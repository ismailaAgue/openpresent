"""
PPTX Export adapter — Technical Blueprint Section 3.5 / 7.

Revision (ADR-024): applies real typography and visual polish for the
first time. Previously, only the title's text COLOR was ever set —
font family, body text size, and every custom-layout textbox's font
were left completely unstyled (font.name=None, font.size=None),
meaning every deck rendered in PowerPoint's bare default look
regardless of the Theme chosen by the Design Engine. `Theme.font_set_id`
had existed since Phase 1 and was never actually read anywhere. This
was the real cause of "mediocre quality" feedback — a structure and
layout problem had already been solved (ADR-020/022/023), but the
underlying visual design was never built, only planned for.

Fixed here: a real font family per theme, consistent sizing across
every text element (title, body bullets, and every custom-layout
textbox), and a simple accent-colored bar under each title as a
visual anchor — the smallest addition that makes a deck read as
"designed" rather than "default," without adding image/AI complexity.
"""

import io
from backend.ports.export import ExportPort
from backend.models.recipe import Recipe, BlockType
from backend.layout.layout_classifier import PROCESS_BULLET_PATTERN

_COLOR_SETS = {
    "neutral": {
        "title": (0x22, 0x22, 0x22), "accent": (0x2E, 0x5C, 0x8A),
        "background": (0xF7, 0xF7, 0xF4),
    },
    "blue_academic": {
        "title": (0x1B, 0x3A, 0x5C), "accent": (0xC8, 0x6B, 0x2E),
        "background": (0xF1, 0xF4, 0xF8),
    },
}

# Office-native fonts only — guarantees consistent rendering across
# any real PowerPoint install, rather than a font that might not be
# present and silently falls back to something else.
_FONT_SETS = {
    "sans": "Calibri",
    "serif": "Cambria",
}

TITLE_SLIDE_FONT_SIZE = 54
CONTENT_TITLE_FONT_SIZE = 40
BODY_FONT_SIZE = 20

# "Measure the title before deciding the layout" — a long title in a
# narrower column (when sharing the slide with an image) was measured
# overflowing past the bottom of the slide at a fixed 54pt. Scaling
# font size down by title length is simple, deterministic, and doesn't
# depend on whether a given renderer honors PowerPoint's autofit
# (LibreOffice's autofit fidelity is inconsistent; a computed size is
# correct everywhere, always).
def _fitting_title_font_size(title: str, base_size: int, narrow_column: bool) -> int:
    length = len(title)
    if narrow_column:
        if length > 70:
            ratio = 0.44
        elif length > 45:
            ratio = 0.56
        elif length > 28:
            ratio = 0.67
        else:
            ratio = 1.0
    else:
        if length > 70:
            ratio = 0.6
        elif length > 45:
            ratio = 0.8
        else:
            ratio = 1.0
    return max(18, int(base_size * ratio))  # never shrink below a readable floor


class PptxExportAdapter(ExportPort):
    def format_id(self) -> str:
        return "pptx"

    def export(self, recipe: Recipe) -> bytes:
        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt, Emu
            from pptx.dml.color import RGBColor
            from pptx.enum.text import PP_ALIGN
            from pptx.enum.shapes import MSO_SHAPE
        except ImportError as e:
            raise RuntimeError(
                "python-pptx is required for PPTX export. Install with: "
                "pip install python-pptx --break-system-packages"
            ) from e

        colors = _COLOR_SETS.get(recipe.theme.color_set_id, _COLOR_SETS["neutral"])
        title_color = RGBColor(*colors["title"])
        accent_color = RGBColor(*colors["accent"])
        background_color = RGBColor(*colors["background"])
        font_name = _FONT_SETS.get(recipe.theme.font_set_id, _FONT_SETS["sans"])

        # Lazy import to avoid a circular dependency — registry.py
        # imports this module to construct PptxExportAdapter, so this
        # module can't import registry at the top level.
        from backend.adapters import registry as _registry
        media = _registry.get_media_adapter()

        ctx = _RenderContext(
            Inches=Inches, Pt=Pt, Emu=Emu, RGBColor=RGBColor, PP_ALIGN=PP_ALIGN,
            MSO_SHAPE=MSO_SHAPE, title_color=title_color, accent_color=accent_color,
            background_color=background_color, font_name=font_name, media=media,
        )

        prs = Presentation()
        content_layout = prs.slide_layouts[1]
        # "Title Only" layout (index 5 in the default template) — gives
        # a title placeholder with an empty body, so every specialized
        # layout (title slide, statistics, comparison, process, and
        # now bullet+image) can place shapes at explicitly-computed,
        # verified-non-overlapping positions instead of relying on a
        # fixed template placeholder that doesn't account for an image
        # sharing the slide (ADR-026 — see module docstring).
        title_only_layout = prs.slide_layouts[5]

        for i, slide_data in enumerate(sorted(recipe.outline.slides, key=lambda s: s.order)):
            is_title_slide = (i == 0)
            if is_title_slide:
                self._render_title_slide(prs, title_only_layout, slide_data, ctx)
                continue

            body_texts = [
                b.text for b in slide_data.content_blocks
                if b.type in (BlockType.BULLET, BlockType.NOTE) and b.text
            ]

            if slide_data.layout_type == "comparison" and body_texts:
                self._render_comparison_slide(prs, title_only_layout, slide_data.title, body_texts, ctx)
            elif slide_data.layout_type == "process" and body_texts:
                self._render_process_slide(prs, title_only_layout, slide_data.title, body_texts, ctx)
            elif slide_data.layout_type == "statistics" and body_texts:
                self._render_statistics_slide(prs, title_only_layout, slide_data.title, body_texts, ctx)
            else:
                image_query = getattr(slide_data, "image_query", None)
                self._render_bullet_slide(prs, content_layout, title_only_layout, slide_data.title,
                                           body_texts, ctx, media=ctx.media, image_query=image_query)

        buf = io.BytesIO()
        prs.save(buf)
        return buf.getvalue()

    # -- shared helpers ---------------------------------------------------

    def _add_title_with_accent(self, slide, ctx, title):
        """Sets a styled content-slide title and adds a thin accent-
        colored bar beneath it. (The pptx design skill flags accent
        bars as a common AI-slop pattern — noted, but kept here per
        explicit product decision: it's a deliberate visual identity
        choice, not an oversight.) Used by every layout so all of them
        read as one consistent product."""
        slide.shapes.title.text = title
        fitted_size = _fitting_title_font_size(title, CONTENT_TITLE_FONT_SIZE, narrow_column=False)
        ctx.style_run(slide.shapes.title.text_frame.paragraphs[0],
                       size=fitted_size, color=ctx.title_color, bold=True)

        title_shape = slide.shapes.title
        bar_top = title_shape.top + title_shape.height + ctx.Emu(45000)
        bar = slide.shapes.add_shape(
            ctx.MSO_SHAPE.RECTANGLE, title_shape.left, bar_top, ctx.Inches(1.4), ctx.Pt(4)
        )
        bar.fill.solid()
        bar.fill.fore_color.rgb = ctx.accent_color
        bar.line.fill.background()
        bar.shadow.inherit = False

    def _apply_background(self, slide, ctx):
        """Tier 1 visual improvement: a real background fill instead of
        plain white on every slide, per the theme's background color.
        Cheap, pure-rules, and directly addresses one of the clearest
        gaps versus the reference decks (which never use plain white)."""
        if ctx.background_color is None:
            return
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = ctx.background_color

    def _add_corner_decoration(self, slide, ctx):
        """Tier 1 visual improvement: a simple geometric accent shape
        in a slide corner — cheap to draw, adds visual interest without
        needing any image, and is a real (if modest) step toward the
        "don't create text-only slides" guidance, ahead of Tier 2's
        real image integration."""
        size = ctx.Inches(0.9)
        shape = slide.shapes.add_shape(
            ctx.MSO_SHAPE.OVAL, ctx.Inches(-0.3), ctx.Inches(-0.3), size, size
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = ctx.accent_color
        shape.line.fill.background()
        shape.shadow.inherit = False

    # -- layout renderers ------------------------------------------------

    def _render_bullet_slide(self, prs, content_layout, title_only_layout, title, body_texts, ctx, media=None, image_query=None):
        image_bytes = self._maybe_fetch_image(media, image_query)

        if image_bytes and body_texts:
            # Uses title_only_layout + manually-positioned shapes, same
            # as every other specialized layout — NOT the native content
            # placeholder. Resizing an inherited placeholder's left/width
            # without also setting top/height corrupts its position
            # (found via real testing — ADR-026): the body placeholder
            # serialized with height=0 and top=0, landing directly under
            # the title instead of below it. Manual textboxes with fully
            # explicit geometry sidestep that class of bug entirely.
            self._render_bullet_slide_with_image(prs, title_only_layout, title, body_texts, image_bytes, ctx)
            return

        # No image (or no media adapter configured) — the plain,
        # unchanged path using the native placeholder, which is never
        # resized and so was never affected by the bug above.
        slide = prs.slides.add_slide(content_layout)
        self._apply_background(slide, ctx)
        self._add_title_with_accent(slide, ctx, title)

        if not body_texts or len(slide.placeholders) < 2:
            return

        body_placeholder = slide.placeholders[1]
        tf = body_placeholder.text_frame
        tf.word_wrap = True
        tf.text = body_texts[0]
        ctx.style_run(tf.paragraphs[0], size=BODY_FONT_SIZE)
        for extra in body_texts[1:]:
            p = tf.add_paragraph()
            p.text = extra
            p.level = 0
            ctx.style_run(p, size=BODY_FONT_SIZE)

    def _render_bullet_slide_with_image(self, prs, title_only_layout, title, body_texts, image_bytes, ctx):
        """Text on the left, image on the right — both positioned
        explicitly below the title's REAL bottom edge (read after the
        title is actually placed, not assumed), guaranteeing no
        title/content/image overlap by construction rather than by
        coincidence (ADR-026 — this is the fix for the confirmed P0
        collision bug found via real generated output)."""
        slide = prs.slides.add_slide(title_only_layout)
        self._apply_background(slide, ctx)
        self._add_title_with_accent(slide, ctx, title)

        title_shape = slide.shapes.title
        # Real measured bottom edge of the title, plus clearance for
        # the accent bar beneath it — not a guessed constant.
        content_top = title_shape.top + title_shape.height + ctx.Inches(0.3)

        slide_width, slide_height = prs.slide_width, prs.slide_height
        margin = ctx.Inches(0.5)
        gutter = ctx.Inches(0.3)
        bottom_margin = ctx.Inches(0.4)
        image_width = ctx.Inches(4.0)
        text_width = slide_width - margin - gutter - image_width - margin
        content_height = slide_height - content_top - bottom_margin

        text_box = slide.shapes.add_textbox(margin, content_top, text_width, content_height)
        tf = text_box.text_frame
        tf.word_wrap = True
        tf.text = body_texts[0]
        ctx.style_run(tf.paragraphs[0], size=BODY_FONT_SIZE)
        for extra in body_texts[1:]:
            p = tf.add_paragraph()
            p.text = extra
            ctx.style_run(p, size=BODY_FONT_SIZE)

        image_left = margin + text_width + gutter
        self._add_picture_capped(slide, ctx, image_bytes, image_left, content_top, image_width, content_height)

    def _add_picture_capped(self, slide, ctx, image_bytes, left, top, max_width, max_height):
        """Adds a picture sized to max_width, then shrinks it
        proportionally (preserving aspect ratio) if its natural height
        would exceed max_height — guarantees an image can never extend
        past its allotted region regardless of its native aspect ratio,
        which is what actually prevents overlap, not just a width cap."""
        import io as _io
        pic = slide.shapes.add_picture(_io.BytesIO(image_bytes), left, top, width=max_width)
        if pic.height > max_height:
            scale = max_height / pic.height
            pic.height = int(pic.height * scale)
            pic.width = int(pic.width * scale)
            pic.left = left  # re-anchor left edge; only height/width shrank
        return pic

    def _maybe_fetch_image(self, media, image_query):
        """Never raises, never blocks the deck on a failed/missing
        image — same graceful-degradation discipline as the AI Port
        (Constitution Principle 3, extended to media in ADR-025)."""
        if media is None or image_query is None:
            return None
        try:
            if not media.is_available():
                return None
            return media.search_image(image_query)
        except Exception:
            return None

    def _render_title_slide(self, prs, title_only_layout, slide_data, ctx):
        """Title text and (optional) image are both positioned
        explicitly, in the same left-column/right-column scheme as
        every other layout — NOT the default 'Title Slide' template's
        fixed placeholder positions, which is what caused the
        confirmed P0 collision bug: that template's title box sits at
        a fixed vertical position regardless of content, and the old
        code placed the image at an independently-chosen fixed
        position with no check that the two didn't overlap. They did,
        on every single deck. Fixed here by computing both boxes from
        the same coordinate scheme, so overlap is structurally
        impossible rather than avoided by a lucky constant (ADR-026)."""
        slide = prs.slides.add_slide(title_only_layout)
        self._apply_background(slide, ctx)
        self._add_corner_decoration(slide, ctx)

        image_bytes = self._maybe_fetch_image(ctx.media, getattr(slide_data, "image_query", None))
        slide_width, slide_height = prs.slide_width, prs.slide_height
        margin = ctx.Inches(0.6)

        if image_bytes:
            gutter = ctx.Inches(0.4)
            image_width = ctx.Inches(4.2)
            title_width = slide_width - margin - gutter - image_width - margin
            title_top = int(slide_height * 0.28)
            title_height = int(slide_height * 0.62)  # generous — most of the remaining vertical space

            title_box = slide.shapes.add_textbox(margin, title_top, title_width, title_height)
            tf = title_box.text_frame
            tf.word_wrap = True
            tf.text = slide_data.title
            fitted_size = _fitting_title_font_size(slide_data.title, TITLE_SLIDE_FONT_SIZE, narrow_column=True)
            ctx.style_run(tf.paragraphs[0], size=fitted_size, color=ctx.title_color, bold=True)

            image_left = margin + title_width + gutter
            image_top = ctx.Inches(0.6)
            image_max_height = slide_height - image_top - ctx.Inches(0.6)
            self._add_picture_capped(slide, ctx, image_bytes, image_left, image_top, image_width, image_max_height)
        else:
            title_top = int(slide_height * 0.32)
            title_height = int(slide_height * 0.55)
            title_box = slide.shapes.add_textbox(margin, title_top, slide_width - (2 * margin), title_height)
            tf = title_box.text_frame
            tf.word_wrap = True
            tf.text = slide_data.title
            fitted_size = _fitting_title_font_size(slide_data.title, TITLE_SLIDE_FONT_SIZE, narrow_column=False)
            ctx.style_run(tf.paragraphs[0], size=fitted_size, color=ctx.title_color, bold=True)

    def _render_statistics_slide(self, prs, title_only_layout, title, body_texts, ctx):
        """Large, centered callouts arranged in a row instead of a
        bulleted list — appropriate for slides that are mostly a
        handful of key numbers (Layout Classifier: ADR-022)."""
        slide = prs.slides.add_slide(title_only_layout)
        self._apply_background(slide, ctx)
        self._add_title_with_accent(slide, ctx, title)

        stats = body_texts[:4]  # beyond 4, a row stops being readable at a glance
        slide_width, slide_height = prs.slide_width, prs.slide_height
        margin = ctx.Inches(0.5)
        box_width = (slide_width - (2 * margin)) // len(stats)
        box_top = int(slide_height * 0.42)
        box_height = ctx.Inches(2.2)

        for idx, stat_text in enumerate(stats):
            left = margin + (idx * box_width)
            box = slide.shapes.add_textbox(left, box_top, box_width, box_height)
            tf = box.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = stat_text
            p.alignment = ctx.PP_ALIGN.CENTER
            ctx.style_run(p, size=22, color=ctx.accent_color, bold=True)

    def _render_comparison_slide(self, prs, title_only_layout, title, body_texts, ctx):
        """Two side-by-side text columns instead of one bulleted list —
        for slides whose title signals a direct comparison ('X vs Y'),
        per the Layout Classifier (ADR-022)."""
        slide = prs.slides.add_slide(title_only_layout)
        self._apply_background(slide, ctx)
        self._add_title_with_accent(slide, ctx, title)

        midpoint = max(1, len(body_texts) // 2) if len(body_texts) > 1 else len(body_texts)
        left_items, right_items = body_texts[:midpoint], body_texts[midpoint:]

        slide_width, slide_height = prs.slide_width, prs.slide_height
        margin, gutter = ctx.Inches(0.5), ctx.Inches(0.3)
        column_width = (slide_width - (2 * margin) - gutter) // 2
        top = int(slide_height * 0.36)
        height = ctx.Inches(3.5)

        for items, left in ((left_items, margin), (right_items, margin + column_width + gutter)):
            box = slide.shapes.add_textbox(left, top, column_width, height)
            tf = box.text_frame
            tf.word_wrap = True
            if not items:
                continue
            tf.text = items[0]
            ctx.style_run(tf.paragraphs[0], size=16)
            for extra in items[1:]:
                p = tf.add_paragraph()
                p.text = extra
                ctx.style_run(p, size=16)

    def _render_process_slide(self, prs, title_only_layout, title, body_texts, ctx):
        """Numbered step boxes arranged left to right instead of a flat
        bulleted list, per the Layout Classifier (ADR-023)."""
        slide = prs.slides.add_slide(title_only_layout)
        self._apply_background(slide, ctx)
        self._add_title_with_accent(slide, ctx, title)

        steps = body_texts[:5]  # beyond 5, a single row stops being readable
        slide_width, slide_height = prs.slide_width, prs.slide_height
        margin = ctx.Inches(0.4)
        box_width = (slide_width - (2 * margin)) // len(steps)
        number_top = int(slide_height * 0.36)
        number_height = ctx.Inches(0.6)
        text_top = number_top + number_height
        text_height = ctx.Inches(2.4)

        for idx, step_text in enumerate(steps):
            left = margin + (idx * box_width)
            cleaned_text = PROCESS_BULLET_PATTERN.sub("", step_text).lstrip(",: ").strip()
            cleaned_text = cleaned_text[0].upper() + cleaned_text[1:] if cleaned_text else step_text

            number_box = slide.shapes.add_textbox(left, number_top, box_width, number_height)
            np = number_box.text_frame.paragraphs[0]
            np.text = str(idx + 1)
            np.alignment = ctx.PP_ALIGN.CENTER
            ctx.style_run(np, size=28, color=ctx.accent_color, bold=True)

            text_box = slide.shapes.add_textbox(left, text_top, box_width, text_height)
            tf = text_box.text_frame
            tf.word_wrap = True
            tp = tf.paragraphs[0]
            tp.text = cleaned_text
            tp.alignment = ctx.PP_ALIGN.CENTER
            ctx.style_run(tp, size=14)


class _RenderContext:
    """Bundles the python-pptx types and theme values every renderer
    needs, plus a single helper for applying font family/size/color/
    bold consistently — this is what guarantees every layout looks
    like one coherent product instead of four independently-styled
    experiments (the actual root cause behind the "mediocre quality"
    feedback: nothing enforced consistency before this)."""

    def __init__(self, Inches, Pt, Emu, RGBColor, PP_ALIGN, MSO_SHAPE,
                 title_color, accent_color, background_color, font_name, media=None):
        self.Inches = Inches
        self.Pt = Pt
        self.Emu = Emu
        self.RGBColor = RGBColor
        self.PP_ALIGN = PP_ALIGN
        self.MSO_SHAPE = MSO_SHAPE
        self.title_color = title_color
        self.accent_color = accent_color
        self.background_color = background_color
        self.font_name = font_name
        self.media = media

    def style_run(self, paragraph, size=None, color=None, bold=None):
        """Applies the theme font family to a paragraph's font
        (covers the whole paragraph even before individual runs
        exist, since python-pptx creates the run from paragraph.text
        assignment) plus any explicitly requested size/color/bold."""
        paragraph.font.name = self.font_name
        if size is not None:
            paragraph.font.size = self.Pt(size)
        if color is not None:
            paragraph.font.color.rgb = color
        if bold is not None:
            paragraph.font.bold = bold
