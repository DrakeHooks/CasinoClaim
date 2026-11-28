# Drake Hooks + WaterTrooper
# Casino Claim 3
# Shared consent and claim-state helpers

# ─────────────────────────────────────────────────────────────
# Generic DOM helpers
# ─────────────────────────────────────────────────────────────

_DOM = r"""
const norm = s => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
const text = e => norm(e.innerText || '');
const visible = e => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' &&
        s.display !== 'none' && s.opacity !== '0' &&
        !e.closest('[hidden], [aria-hidden="true"], [inert]');
};
const enabled = e => !e.disabled && !e.closest('[disabled], [aria-disabled="true"]');
const label = e => text(e) || norm(e.getAttribute('aria-label')) || norm(e.value);
const controls = 'button, [role="button"], input[type="button"]';
const google = t => /connect (with|on|your) google|google grab|google account|google rewards|lucrative bonus|sign in with google/i.test(t);
const purchase = t => /checkout|payment method|order summary|purchase|buy now|credit card|\$\s*\d/i.test(t);
const area = e => { const r = e.getBoundingClientRect(); return r.width * r.height; };
const overlay = e => e.matches('[role="dialog"], [aria-modal="true"], dialog') ||
    /fixed|sticky/.test(getComputedStyle(e).position) ||
    /modal|popup|dialog|overlay|banner|consent/i.test(String(e.className || '') + ' ' + e.id);
const unavailable = t => /already (claimed|collected)|daily bonus (is )?(claimed|unavailable)|today.s bonus (is )?claimed|come back tomorrow|see you tomorrow|next (daily )?(bonus|claim|reward)|available in\s+\d|\b\d{1,2}:\d{2}:\d{2}\b/i.test(t);
"""


def _scan(sb, script, default=None):
    try:
        return sb.execute_script(_DOM + script)
    except Exception as error:
        print(f"[Claim State] DOM observation failed: {type(error).__name__}")
        return default


# ─────────────────────────────────────────────────────────────
# Cookie/privacy consent
# ─────────────────────────────────────────────────────────────

def accept_cookie_banner(sb, passes=4):
    """Accept genuine cookie consent controls without hiding overlays."""
    for _ in range(passes):
        button = _scan(sb, r"""
            const candidates = [];
            for (const button of [...document.querySelectorAll(controls + ', a')].filter(visible).filter(enabled)) {
                if (!/^(accept all( cookies)?|accept cookies|allow all( cookies)?|accept|i agree|agree|accept all and continue)$/.test(label(button))) continue;
                for (let p = button.parentElement, i = 0; p && i < 8 && p !== document.body; p = p.parentElement, i++) {
                    const t = text(p);
                    if (t.length > 1800) break;
                    if (/(we value your privacy|cookie preferences|manage cookies|we use cookies|cookie consent|privacy preferences)/.test(t)
                        && (overlay(p) || /manage cookies|we use cookies/.test(t))) {
                        candidates.push({button, score: area(p)});
                        break;
                    }
                }
            }
            candidates.sort((a,b) => a.score-b.score);
            return candidates.length ? candidates[0].button : null;
        """)
        if button is not None:
            try:
                button.click()
                print("[Claim State] Accepted visible cookie/privacy banner.")
                sb.wait(0.5)
                return True
            except Exception as error:
                print(f"[Claim State] Cookie click blocked: {type(error).__name__}")
        sb.wait(0.5)
    return False


def login_form_visible(sb):
    return _scan(sb, r"""
        return [...document.querySelectorAll('input[type="password"]')].some(visible);
    """, True)


# ─────────────────────────────────────────────────────────────
# Scoped Google prompt and claim confirmation
# ─────────────────────────────────────────────────────────────

def close_google_prompt(sb):
    button = _scan(sb, r"""
        const roots = [...document.querySelectorAll('div, section, dialog')]
            .filter(visible).filter(overlay).filter(e => {
                const t = text(e);
                return t.length < 1000 && google(t) &&
                    /connect (with|on|your) google|google grab/.test(t);
            }).sort((a,b) => area(a)-area(b));
        for (const root of roots) {
            const close = [...root.querySelectorAll('button, [role="button"], [aria-label], [title], [class*="close" i]')]
                .filter(visible).filter(enabled).find(e =>
                    /^(close|dismiss|x|×|✕|✖)$/.test(label(e)) ||
                    /^(close|dismiss)( dialog| popup)?$/.test(norm(e.getAttribute('aria-label'))) ||
                    /(^|[\s_-])close($|[\s_-])/i.test(String(e.className || '')));
            if (close) return close;
        }
        return null;
    """)
    if button is None:
        return False
    try:
        button.click()
        sb.wait(0.5)
        print("[Claim State] Closed unrelated Google-connect prompt.")
        return True
    except Exception:
        return False


def reward_success_signatures(sb):
    """Capture compact, visible receipts; compare before and after the click."""
    return set(_scan(sb, r"""
        const nodes = [...document.querySelectorAll('div, section, dialog, [role="status"], [role="alert"]')].filter(visible);
        const matches = nodes.filter(e => {
            const t = text(e);
            if (!t || t.length > 800 || google(t) || purchase(t) ||
                /already (claimed|collected)|not claimed|unable to claim|failed to claim/.test(t)) return false;
            const receipt = /congratulations/.test(t) &&
                /you have received free (gc and sc|sc and gc|gc|sc)\b/.test(t);
            const explicit = /daily bonus (has been |was |is )?(successfully )?(claimed|collected)|successfully (claimed|collected) (your |the )?daily bonus/.test(t);
            return (receipt || explicit) && (overlay(e) ||
                e.matches('[role="status"], [role="alert"], [class*="toast" i]') ||
                (receipt && /start playing/.test(t)));
        });
        return [...new Set(matches.filter(e => !matches.some(other =>
            other !== e && e.contains(other))).map(text))];
    """, []) or [])


# ─────────────────────────────────────────────────────────────
# Daily Bonus card candidacy
# ─────────────────────────────────────────────────────────────

def daily_card_snapshot(sb):
    """Return only identifiable daily cards, never generic Collect controls."""
    return _scan(sb, r"""
        const cardSelector = '.coin-store-reward-package, [data-sentry-component="CoinStoreRewardPackage"], .free-reward-card, .coin-store-free-rewards-row-item, [class*="daily-bonus" i], [class*="reward-package" i], [class*="reward-card" i]';
        const isDaily = t => /\b(daily bonus|daily reward|today.s bonus|todays bonus)\b/.test(t);
        const roots = new Set([...document.querySelectorAll(cardSelector)].filter(visible));
        for (const heading of document.querySelectorAll('h1,h2,h3,h4,h5,span,p,div')) {
            if (!visible(heading) || !/^(progressive )?(daily bonus|daily reward|today.s bonus|todays bonus)$/.test(text(heading))) continue;
            for (let p = heading.parentElement, i = 0; p && i < 6 && p !== document.body; p = p.parentElement, i++) {
                const t = text(p);
                if (t.length > 700 || google(t) || purchase(t)) break;
                if (p.querySelector(controls) || unavailable(t)) {
                    roots.add(p);
                    break;
                }
            }
        }
        const daily = [...roots].filter(e => {
            const t = text(e);
            return t.length <= 700 && isDaily(t) && !google(t) && !purchase(t) &&
                !/daily bonus is ready|go to (the )?coin store/.test(t) &&
                (e.querySelector(controls) || unavailable(t));
        }).filter(e => e.closest('[role="dialog"], [aria-modal="true"], dialog, [class*="coin-store" i], [class*="free-coin-dialog" i]') || e.matches(cardSelector));
        const cards = daily.filter(e => !daily.some(other => other !== e && e.contains(other)));
        const results = cards.map(e => {
            const t = text(e);
            const active = [...e.querySelectorAll(controls)].filter(visible).filter(enabled).filter(b =>
                /^(collect|collect now|claim|claim now|claim daily bonus|collect daily bonus)$/.test(label(b)));
            return {text:t, unavailable:unavailable(t), enabled:active.length,
                    button:active.length === 1 ? active[0] : null};
        });
        return {count:results.length, card:results.length === 1 ? results[0] : null};
    """, {"count": 0, "card": None})


def wait_for_daily_confirmation(sb, before_signatures, observe_card, seconds=12):
    """Require a new receipt or a persistent explicit daily-card transition."""
    stable = 0
    for _ in range(int(seconds * 2)):
        if reward_success_signatures(sb) - before_signatures:
            return True
        if observe_card():
            stable += 1
            if stable >= 3:
                return True
        else:
            stable = 0
        sb.wait(0.5)
    return False
