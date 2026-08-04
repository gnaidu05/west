// Supabase Edge Function: invite-user
//
// Admin-only. Creates a confirmed auth user with a generated temporary
// password, writes their profiles row (role + scope), and emails the temp
// password via Resend. The service_role key lives only here (server-side) —
// never in the static page.
//
// Deploy:  supabase functions deploy invite-user
// Secrets (Project Settings -> Edge Functions, or `supabase secrets set`):
//   RESEND_API_KEY   your Resend API key
//   INVITE_FROM      verified sender, e.g. "West Zone Portal <invites@yourdomain>"
//   PORTAL_URL       https://gnaidu05.github.io/west/
// (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are injected automatically.)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

function genPassword(): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%";
  const a = new Uint32Array(14);
  crypto.getRandomValues(a);
  return Array.from(a, (x) => alphabet[x % alphabet.length]).join("");
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const url = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const admin = createClient(url, serviceKey, { auth: { persistSession: false } });

  // 1) authenticate the caller and require the admin role
  const token = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!token) return json({ error: "missing token" }, 401);
  const { data: udata, error: uErr } = await admin.auth.getUser(token);
  if (uErr || !udata?.user) return json({ error: "unauthorized" }, 401);
  const { data: prof } = await admin.from("profiles").select("role").eq("id", udata.user.id).single();
  if (prof?.role !== "admin") return json({ error: "admin only" }, 403);

  // 2) validate input
  let body: { email?: string; role?: string; scope?: string; name?: string };
  try { body = await req.json(); } catch { return json({ error: "bad json" }, 400); }
  const email = (body.email || "").trim().toLowerCase();
  const role = (body.role || "").trim();
  const scope = (body.scope || "").trim() || null;
  const name = (body.name || "").trim() || email;
  if (!email || !/^\S+@\S+\.\S+$/.test(email)) return json({ error: "valid email required" }, 400);
  if (!["admin", "spoc", "tpo"].includes(role)) return json({ error: "role must be admin/spoc/tpo" }, 400);
  if (role !== "admin" && !scope) return json({ error: "scope required for spoc/tpo" }, 400);

  // 3) create the confirmed user with a temp password
  const tempPassword = genPassword();
  const { data: created, error: cErr } = await admin.auth.admin.createUser({
    email, password: tempPassword, email_confirm: true,
  });
  if (cErr || !created?.user) return json({ error: cErr?.message || "create failed" }, 400);
  const newId = created.user.id;

  // 4) upsert the role row
  const { error: pErr } = await admin.from("profiles")
    .upsert({ id: newId, role, scope, name }, { onConflict: "id" });
  if (pErr) return json({ error: "user created but profile failed: " + pErr.message, userId: newId, tempPassword }, 500);

  // 5) email the temp password via Resend (fall back to returning it)
  const resendKey = Deno.env.get("RESEND_API_KEY");
  const from = Deno.env.get("INVITE_FROM") || "West Zone Portal <onboarding@resend.dev>";
  const portal = Deno.env.get("PORTAL_URL") || "https://gnaidu05.github.io/west/";
  let emailed = false, emailError: string | null = null;
  if (resendKey) {
    const text =
`Hi ${name},

An account has been created for you on the West Zone campus hiring portal.

Portal:   ${portal}
Email:    ${email}
Password: ${tempPassword}

Please sign in and change your password right away (the "Password" button in the top bar).

Your access: ${role}${scope ? ` — ${scope}` : ""}.${role !== "admin" ? " Your edits are submitted to the admin for approval before they publish." : ""}

Thanks,
West Zone Campus Team`;
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${resendKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({ from, to: [email], subject: "Your West Zone Portal login", text }),
    });
    emailed = r.ok;
    if (!r.ok) emailError = (await r.text()).slice(0, 300);
  } else {
    emailError = "RESEND_API_KEY not set";
  }

  // if the email went out, don't return the password; otherwise return it so
  // the admin can pass it on manually
  return json({ ok: true, userId: newId, emailed, emailError, tempPassword: emailed ? undefined : tempPassword });
});
