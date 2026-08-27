import { redirect } from "next/navigation";

// The studio experience (chat + sidebar + preview) moved to the site
// root ("/") — it's the product's main page now, not a sub-route.
// This stub exists only so anyone with an old /studio bookmark or
// browser-history entry from testing lands somewhere real instead of
// a 404, rather than being deleted outright.
export default function StudioRedirectPage() {
  redirect("/");
}
