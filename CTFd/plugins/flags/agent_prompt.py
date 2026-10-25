"""
Builds a copy-paste prompt that tells a challenge author's AI agent exactly how
to mint dynamic flags that CTFd will accept. The reference code embedded in the
prompt is the real dynamic.py, so the two can never drift apart.
"""

import inspect

from CTFd.plugins.flags import dynamic

EXAMPLE_TEAMS = ("hello", "  Team   ARGO ")

BIND_TEXT = {
    "team_name": "the team's CTFd team name",
    "team_id": 'the team\'s numeric CTFd team id, as a string (e.g. "7")',
    "user_name": "the player's CTFd username",
    "user_id": 'the player\'s numeric CTFd user id, as a string (e.g. "42")',
}


def build(base, secret="", length=dynamic.DEFAULT_LENGTH, bind="team_name"):
    base = (base or "").strip() or "<FLAG>"
    have_secret = dynamic.is_valid_secret(secret)
    key = secret if have_secret else "<SECRET_KEY - copy it from the CTFd flag screen>"
    shape = dynamic.place_tag(base, "<TAG>")
    who = BIND_TEXT.get(bind, BIND_TEXT["team_name"])

    if have_secret:
        rows = "\n".join(
            f"  identity {name!r:<20} -> {dynamic.make_flag(secret, name, base, length)}"
            for name in EXAMPLE_TEAMS
        )
        examples = (
            "Worked examples (your implementation MUST reproduce these exactly):\n"
            f"{rows}\n"
            "Note the second one: the identity is normalised before hashing, so "
            "case and extra spaces do not matter."
        )
    else:
        examples = (
            "Worked examples: none yet, because the secret key is not known. Once "
            "you have the key, check your output against CTFd's \"Check a team's "
            "flag\" box on the flag's edit screen."
        )

    return f"""You are helping build a CTF challenge whose flag is DYNAMIC: every team gets a different flag, and CTFd rejects a flag that was made for another team. Implement the flag generation EXACTLY as specified below. Do not change, simplify or "improve" the algorithm. Any difference means every team's flag will be rejected.

== Flag settings (from CTFd) ==
Base flag:   {base}
Secret key:  {key}
Tag length:  {length} hex characters
Identity:    {who}
Flag shape:  {shape}

== Algorithm ==
1. identity = {who}.
2. Normalise it: Unicode NFKC, then casefold (lowercase), then trim leading/trailing whitespace, then collapse every run of whitespace into a single space.
3. tag = HMAC-SHA256(key = bytes.fromhex(SECRET_KEY), message = normalised identity encoded as UTF-8), as lowercase hex, keeping only the first {length} characters.
4. Insert the tag into the base flag:
   - if the base contains %TAG%, replace %TAG% with the tag;
   - otherwise insert "_" + tag just before the LAST "}}";
   - if there is no "}}", append "_" + tag to the end.
   The separator is a single underscore. Do not change the case of the base flag.

== Reference implementation (use this file as-is; it is the code CTFd runs) ==
```python
{inspect.getsource(dynamic).strip()}
```
Generate a team's flag with:
```python
flag = make_flag(SECRET_KEY, identity, {base!r}, {length})
```

{examples}

== Rules for the challenge ==
- The challenge must know {who} at the moment it hands out the flag (for example, ask the player to enter it, or receive it from your service). Hand out ONLY that team's flag. Remind players to use their EXACT CTFd team name.
- Dynamic flags need code that runs when the flag is handed out (a server, bot or generator). A single static file that every team downloads cannot contain a per-team flag.
- Keep the secret key on the server side only (environment variable or a file that is not served). Never put it in files, client-side code, images or repos that players can see. Anyone with the key can mint any team's flag.
- Do not log or print other teams' flags where players can see them.
- Before finishing, write a test that reproduces the worked examples above and run it.
"""
