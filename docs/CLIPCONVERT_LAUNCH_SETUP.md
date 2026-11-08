# ClipConvert launch configuration

This is a **separate ClipConvert project**. Do not copy SMTP sender addresses,
business ownership, trademarks or legal details from any other brand.

## State verified November 8, 2026

- Live Railway: https://clipconvert-web-production.up.railway.app/
- Connected custom domain: **none**
- Verified ClipConvert sending or receiving domain: **none**
- SMTP host smtp.resend.com, port 465, username resend: configured
- SMTP password, branded sender and recipient: **not configured**
- Contact and rights reports: saved to a protected SQLite inbox for up to 90 days
- Private operator dashboard: /admin (requires ADMIN_TOKEN)
- Email delivery: inactive until dedicated SMTP details are configured
- Legal operating entity, postal address and copyright agent: not designated
- DMCA agent registration: not claimed
- Converted media: typically expires about one hour after completion

## Choose and register a domain

A current Namecheap check returned:
- clipconvert.app — available, purchase price $10.98
- getclipconvert.com — available, purchase price $12.08
- clipconvert.com — unavailable
- clipconvert.io — unavailable

Prices, renewals and availability can change. No registration or purchase was
performed. clipconvert.app is the suggested exact-match brand candidate.

## Connect a verified domain to Railway

After registration:
1. On the ClipConvert Railway service, use Settings > Public Networking > Add Custom Domain.
2. Enter the owned hostname, for example clipconvert.app.
3. Create both Railway's generated CNAME and ownership TXT verification records at
   the DNS provider. Both must be verified before using the custom domain.
4. Wait for a valid HTTPS certificate, then set SITE_URL to the final HTTPS origin.
5. Check the homepage, legal routes, robots.txt, sitemap.xml and canonical/social
   metadata. Keep the original Railway hostname running during verification.
6. Set up redirects only after the new HTTPS hostname actually works.

Official reference: https://docs.railway.com/networking/domains/working-with-domains

## Configure dedicated support email

After the domain is owned:
1. Add and verify the distinct ClipConvert domain in Resend for sending.
2. Configure receiving DNS and a branded support inbox if receiving is wanted.
3. Create a dedicated Resend SMTP API key with appropriate access, and store it
   directly in Railway as the SMTP_PASSWORD variable. Do not commit the secret.
4. Configure these Railway variables for the verified brand:

   - SMTP_HOST = smtp.resend.com (already configured)
   - SMTP_PORT = 465 (already configured)
   - SMTP_USER = resend (already configured)
   - SMTP_PASSWORD = private dedicated Resend SMTP API key
   - SMTP_FROM = notifications@clipconvert.app (example after domain verification)
   - CONTACT_EMAIL = support@clipconvert.app (example, after inbox provisioned)

5. Submit a test support form and a test copyright notice, then inspect the private
   operator inbox and Resend sending status. Failed notifications are retried from
   the persistent outbox with backoff. Until all credentials and verified email
   identities are configured, messages are saved but not emailed.

Official reference: https://resend.com/docs/send-with-smtp

## Final legal-entity and copyright designation

The site now provides more detailed privacy and terms information as well as a
structured copyright report form, but does not claim corporate registration,
DMCA safe harbor or a registered copyright agent. To complete formal operator
and legal details, the owner must identify:
- The actual legal person or organization operating ClipConvert
- Its suitable business mailing address, jurisdiction and required contact details
- Any designated copyright agent's public name, mailing address, email and phone
- Whether formal U.S. Copyright Office agent registration is appropriate and,
  if so, file it using the real operator and agent details

Official resource: https://www.copyright.gov/dmca-directory/

A rights-report form alone does not register a statutory agent or guarantee safe
harbor. Operator-specific legal language should be reviewed by qualified counsel.

## Important limitations

The existing Railway URL works without a custom domain; the contact and rights
forms work without email delivery. Long-lived public file storage is deliberately
not enabled: a permanent media library would need authentication, storage budgets,
privacy controls and rights handling. Do not silently extend media retention
or claim that a custom-domain purchase happened.
