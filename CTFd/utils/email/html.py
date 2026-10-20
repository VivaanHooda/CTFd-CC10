from flask import url_for
from markupsafe import escape

# Email-safe HTML: table layout, inline styles, system fonts. Fluid up to 560px so it
# reads the same in Gmail web, Gmail/Outlook mobile and Apple Mail.
GOLD = "#d9b56b"
GOLD_LIGHT = "#f1d79c"
INK = "#e8dfcc"
MUTED = "#8c826f"
CARD = "#0d0b08"
PAGE = "#000000"
SANS = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def _shell(preheader, eyebrow, heading, paragraphs, button_label, url, note, footer):
    url = escape(url)
    logo = escape(url_for("views.themes", path="img/cc-10-years.png", _external=True))
    body = "".join(
        f'<p style="margin:0 0 16px;font-family:{SANS};font-size:16px;line-height:1.6;color:{INK};">{p}</p>'
        for p in paragraphs
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark light">
<meta name="supported-color-schemes" content="dark light">
<title>{escape(heading)}</title>
<style>
  @media only screen and (max-width: 600px) {{
    .card-pad {{ padding: 32px 22px !important; }}
    .heading {{ font-size: 26px !important; }}
    .btn a {{ display: block !important; }}
  }}
  /* Outlook.com dark mode: keep the gold text instead of letting it be recoloured */
  [data-ogsc] .btn-text {{ color: {GOLD_LIGHT} !important; }}
</style>
</head>
<body style="margin:0;padding:0;background:{PAGE};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{PAGE};">{escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{PAGE}" style="background:{PAGE};">
  <tr>
    <td align="center" style="padding:32px 12px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;">
        <tr>
          <td align="center" style="padding:0 0 24px;">
            <img src="{logo}" width="132" alt="Coding Club &middot; 10 Years" style="display:block;width:132px;max-width:40%;height:auto;border:0;color:{GOLD};font-family:{SANS};font-size:14px;">
          </td>
        </tr>
        <tr>
          <td class="card-pad" bgcolor="{CARD}" style="background:{CARD};border:1px solid #3a3022;border-radius:18px;padding:44px 40px;">
            <p style="margin:0 0 12px;font-family:{SANS};font-size:12px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:{GOLD};">{eyebrow}</p>
            <h1 class="heading" style="margin:0 0 20px;font-family:{SANS};font-size:28px;font-weight:700;line-height:1.25;color:{GOLD_LIGHT};">{escape(heading)}</h1>
            {body}
            <table role="presentation" class="btn" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0 24px;">
              <tr>
                <td align="center" bgcolor="#1a150d" style="border-radius:12px;background:#1a150d;border:1.5px solid {GOLD};">
                  <a class="btn-text" href="{url}" target="_blank" style="display:inline-block;padding:14px 32px;font-family:{SANS};font-size:16px;font-weight:600;color:{GOLD_LIGHT};text-decoration:none;border-radius:12px;">{escape(button_label)} &rarr;</a>
                </td>
              </tr>
            </table>
            <p style="margin:0 0 24px;font-family:{SANS};font-size:14px;line-height:1.6;color:{MUTED};">{note}</p>
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr><td style="border-top:1px solid #2a2319;padding-top:20px;">
                <p style="margin:0 0 6px;font-family:{SANS};font-size:13px;color:{MUTED};">Button not working? Paste this link into your browser:</p>
                <p style="margin:0;font-family:{SANS};font-size:13px;line-height:1.5;word-break:break-all;"><a href="{url}" target="_blank" style="color:{GOLD};text-decoration:underline;">{url}</a></p>
              </td></tr>
            </table>
          </td>
        </tr>
        <tr>
          <td align="center" style="padding:24px 16px 0;font-family:{SANS};font-size:12px;line-height:1.6;color:#5f574a;">{footer}</td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


def verification_email_html(ctf_name, url):
    name = escape(ctf_name or "the CTF")
    return _shell(
        preheader=f"Confirm your email to set sail in {ctf_name or 'the CTF'}.",
        eyebrow="Coding Club RVCE &middot; 10 Years",
        heading="Confirm your email",
        paragraphs=[
            f"Welcome aboard, sailor. One trial stands between you and <strong style=\"color:{GOLD_LIGHT};\">{name}</strong>.",
            "Confirm this address to unlock the challenges and take your place on the scoreboard.",
        ],
        button_label="Confirm my email",
        url=url,
        note="This link expires in 24 hours. You can request a new one from the confirm page after logging in.",
        footer=f"You're receiving this because this address was used to sign up for {name}.<br>"
        "If that wasn't you, ignore this email and no account will be activated.",
    )
