// Supabase Edge Function: reset-password
//
// PUBLIC endpoint (a locked-out user can't be authenticated). Generates a
// Supabase password-recovery link with the admin API and emails it via Gmail
// SMTP — so reset mail is reliable and branded, instead of Supabase's
// rate-limited built-in email. Always returns a generic success so it never
// reveals whether an account exists.
//
// Deploy WITH JWT VERIFICATION OFF (it must be callable without a token):
//   supabase functions deploy reset-password --no-verify-jwt
//   (dashboard: create the function, then Settings -> turn OFF "Verify JWT")
// Secrets (shared with invite-user; set once):
//   PORTAL_URL          https://gnaidu05.github.io/west/
//   GMAIL_USER          your.address@gmail.com
//   GMAIL_APP_PASSWORD  16-char Google App Password
// (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are injected automatically.)
//
// The portal URL must also be in Supabase -> Authentication -> URL
// Configuration -> Redirect URLs so the emailed link returns to the portal.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  let body: { email?: string; redirectTo?: string };
  try { body = await req.json(); } catch { return json({ error: "bad json" }, 400); }
  const email = (body.email || "").trim().toLowerCase();
  if (!email || !/^\S+@\S+\.\S+$/.test(email)) return json({ error: "valid email required" }, 400);

  const url = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const admin = createClient(url, serviceKey, { auth: { persistSession: false } });
  const portal = body.redirectTo || Deno.env.get("PORTAL_URL") || "https://gnaidu05.github.io/west/";

  // generate a recovery link (only succeeds for an existing user)
  let link: string | null = null;
  try {
    const { data, error } = await admin.auth.admin.generateLink({
      type: "recovery", email, options: { redirectTo: portal },
    });
    if (!error) link = data?.properties?.action_link ?? null;
    else console.log("generateLink:", error.message);
  } catch (e) { console.log("generateLink threw:", String((e as Error)?.message || e)); }

  // email the link via Gmail (only if we have one — otherwise stay silent)
  if (link) {
    const gmailUser = Deno.env.get("GMAIL_USER");
    const gmailPass = Deno.env.get("GMAIL_APP_PASSWORD");
    const text =
`Hi,

We received a request to reset your West Zone Portal password.

Open this link to set a new password:
${link}

If you didn't request this, you can ignore this email — your password won't change.
For security, the link expires shortly.

Thanks,
West Zone Campus Team`;
    try {
      if (gmailUser && gmailPass) {
        const { SMTPClient } = await import("https://deno.land/x/denomailer@1.6.0/mod.ts");
        const client = new SMTPClient({
          connection: { hostname: "smtp.gmail.com", port: 465, tls: true, auth: { username: gmailUser, password: gmailPass } },
        });
        await client.send({ from: `West Zone Campus Team <${gmailUser}>`, to: email, subject: "Reset your West Zone Portal password", content: text });
        await client.close();
      } else {
        console.log("reset-password: GMAIL_USER/GMAIL_APP_PASSWORD not set — email not sent");
      }
    } catch (e) { console.log("reset email failed:", String((e as Error)?.message || e)); }
  }

  // never reveal whether the account exists or whether the mail sent
  return json({ ok: true });
});
