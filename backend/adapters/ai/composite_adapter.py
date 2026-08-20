"""
CompositeAIAdapter — ADR-030, cascading fixed for AIPort methods in
ADR-033 (spec Section 6: "future providers should be pluggable...
changing inference backends should not require application rewrites").

Wraps an ORDERED list of configured adapters, implementing both ports:

- AIPipelinePort (topic-first generation): on each stage call, tries
  providers in order — the first available one that succeeds wins; if
  it raises, the composite tries the next configured provider before
  giving up entirely.

- AIPort (document-upload enhancement): ADR-033 fix — this used to
  delegate to the first available provider ONLY, with the (wrong, in
  hindsight) reasoning that these methods "already self-degrade
  internally, so cross-provider cascading adds complexity without
  much benefit." In production this meant: if the first configured
  provider's propose_structure() failed for any reason, the document-
  upload flow silently produced ZERO AI enhancement — every upload
  looked purely rule-based — even with 3 other fully-capable providers
  sitting configured and unused. Now cascades through every provider's
  underlying _*_raising() method (see json_pipeline_base.py's
  _TextEnhancementMixin) exactly like the pipeline stages do, only
  degrading to the original input after every configured provider has
  been tried and failed.
"""

from backend.ports.ai import AIPort
from backend.ports.ai_pipeline import AIPipelinePort
from backend.monitoring.sentry_setup import capture_exception


class CompositeAIAdapter(AIPort, AIPipelinePort):
    def __init__(self, adapters: list):
        # adapters: ordered list of objects implementing both AIPort
        # and AIPipelinePort (Gemini, Groq, OpenRouter, HuggingFace,
        # LocalModel all qualify).
        self.adapters = adapters

    def is_available(self) -> bool:
        return any(a.is_available() for a in self.adapters)

    # -- AIPipelinePort: cascade through providers on failure -----------

    def generate_strategy(self, request, research=None):
        return self._cascade("generate_strategy", request, research)

    def generate_outline_structure(self, request, strategy):
        return self._cascade("generate_outline_structure", request, strategy)

    def generate_slide_content(self, request, strategy, structure):
        return self._cascade("generate_slide_content", request, strategy, structure)

    def plan_layout(self, outline, request):
        return self._cascade("plan_layout", outline, request)

    def review_and_revise(self, outline, report, request):
        return self._cascade("review_and_revise", outline, report, request)

    def regenerate_slide(self, context):
        return self._cascade("regenerate_slide", context)

    def _cascade(self, method_name: str, *args):
        last_error: Exception | None = None
        attempted = False
        for adapter in self.adapters:
            if not adapter.is_available():
                continue
            attempted = True
            try:
                return getattr(adapter, method_name)(*args)
            except Exception as e:
                last_error = e
                continue  # try the next configured provider
        if not attempted:
            raise RuntimeError("no AI provider configured")
        raise last_error or RuntimeError(f"{method_name} failed on every configured provider")

    # -- AIPort: cascade through providers too (ADR-033) -----------------

    def propose_structure(self, outline, source_text, target_slide_count=None):
        return self._cascade_text("_propose_structure_raising", outline, outline,
                                   source_text, target_slide_count)

    def rewrite(self, text, instructions=""):
        return self._cascade_text("_rewrite_raising", text, text, instructions)

    def translate(self, text, target_language):
        return self._cascade_text("_translate_raising", text, text, target_language)

    def summarize(self, text, max_length=None):
        degraded_default = text[:max_length] if max_length else text
        return self._cascade_text("_summarize_raising", degraded_default, text, max_length)

    def suggest(self, context):
        return self._cascade_text("_suggest_raising", [], context)

    def _cascade_text(self, raising_method_name: str, degraded_default, *args):
        """Tries every available provider's raising implementation in
        turn, only falling back to degraded_default (the original,
        unmodified input) once every configured provider has failed —
        this is what makes cascading actually work for AIPort methods,
        unlike pre-ADR-033's "try the first one, silently give up."""
        for adapter in self.adapters:
            if not adapter.is_available():
                continue
            try:
                return getattr(adapter, raising_method_name)(*args)
            except Exception as e:
                capture_exception(e, tags={"stage": "ai_port_cascade",
                                            "method": raising_method_name,
                                            "provider": type(adapter).__name__})
                continue  # try the next configured provider
        return degraded_default  # every provider failed, or none configured
