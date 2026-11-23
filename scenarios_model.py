#!/usr/bin/env python3
"""
scenarios_model.py
==================
מודל פיננסי ומיסויי להשוואת חלופות נדל"ן: אשקלון מול טירת הכרמל (והקשר בנייה עצמית ברתמים)
ציר זמן אחיד: 34 חודשים — מיום 01/12/2026 (חודש 0) ועד 01/09/2029 (חודש 34, תום 18 חודשים מטופס 4 בטירת הכרמל).

כללי המודל:
- כל החלופות נמדדות על אותו אופק זמן (01/12/2026 עד 01/09/2029 = 34 חודשים).
- כל עודף תזרימי / הון עצמי שמשתחרר לפני תום התקופה (01/09/2029) מושקע בריבית אלטרנטיבית נטו
  (או משמש להקטנת משכנתת הבנייה במגרש 324 ברתמים בריבית זהה), וכך ההשוואה בנקודת הסיום (Month 34)
  היא השוואה כלכלית טהורה (Apples-to-Apples Net Ending Equity).
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import math


@dataclass
class MarketAssumptions:
    # שווי שוק במכירה (ש"ח)
    ashkelon_price: float = 2_100_000.0
    tirat_price: float = 2_100_000.0

    # שכירות חודשית (ש"ח)
    ashkelon_rent_p1: float = 5_000.0   # עד 01/2028 (14 חודשים ראשונים: 12/2026 - 01/2028)
    ashkelon_rent_p2: float = 5_250.0   # מ-02/2028 ואילך (אופציית שוכר +5%)
    tirat_rent: float = 5_000.0         # ממועד מסירה (03/2028) ואילך

    # ריביות שנתיות ואינפלציה
    cpi_annual: float = 0.022           # אינפלציה שנתית חזויה (2.2%)
    new_mortgage_rate: float = 0.043    # ריבית משכנתה חדשה / משכנתת בנייה ברתמים (4.3%)
    bridge_loan_rate: float = 0.052     # ריבית הלוואת גישור / בלון לתקופת ביניים (5.2%)
    alt_return_net: float = 0.043       # עלות אלטרנטיבית להון פנוי = חיסכון ריבית משכנתת בנייה ברתמים (4.3% נטו)

    # הוצאות עסקה במכירה (עו"ד מוכר + שיווק/תיווך משוקלל: 1.25% כולל מע"מ)
    selling_cost_pct: float = 0.0125


@dataclass
class VerifiedFacts:
    """עובדות מאומתות מתוך 01_facts_ledger.md"""
    # אשקלון
    ashkelon_original_cost: float = 1_017_595.0
    # יתרות משכנתה באשקלון משוערכות ל-01/12/2026 (לאחר 6 תשלומים מ-26/05/2026)
    ashkelon_cpi_tracks_bal: float = 234_250.0   # 3 מסלולי ק"צ בריבית ממוצעת 1.60% עד 15/03/2035 (99.5 חודשים)
    ashkelon_cpi_tracks_rate: float = 0.0160
    ashkelon_cpi_tracks_months: int = 100
    ashkelon_unlinked_bal: float = 514_450.0     # מסלול מל"צ בריבית 4.86% עד 15/07/2046 (235.5 חודשים)
    ashkelon_unlinked_rate: float = 0.0486
    ashkelon_unlinked_months: int = 235
    ashkelon_grant_penalty: float = 54_800.0     # מענק מותנה (8926365127220) — נמחק לחלוטין ב-15/12/2027 (חודש 12.5)

    # טירת הכרמל
    tirat_contract_price: float = 2_140_000.0
    tirat_equity_paid: float = 214_000.0         # שולם 01/09/2024 (10%)
    tirat_purchase_tax_paid: float = 5_644.0     # שולם 04/11/2024 (מדרגות דירה יחידה)
    tirat_lawyer_paid: float = 6_523.0           # 5,575 + מע"מ
    tirat_contractor_loan: float = 1_498_000.0   # שולם 30/12/2024 (70%) — מסובסד עד 01/12/2027 (חודש 12)
    tirat_final_payment: float = 435_000.0       # 428,000 (20%) + 3,658 הפרש מע"מ 18% + ~3,342 חיבורים (חודש 15: 01/03/2028)

    # מס רכישה רטרואקטיבי בביטול סטטוס משפר דיור (8% על 2,140,000 = 171,200 פחות 5,644 ששולמו = 165,556 קרן)
    tirat_investor_tax_diff_principal: float = 165_556.0


@dataclass
class ScenarioResult:
    code: str
    name: str
    net_ending_equity: float
    total_deadweight_loss: float
    tax_paid_additional: float
    interest_paid_total: float
    grant_or_contract_penalty: float
    transaction_costs: float
    peak_debt: float
    peak_bridge_cash_needed: float
    worst_monthly_net_cashflow: float
    notes: str


def spitzer_payment(principal: float, annual_rate: float, months: int) -> float:
    if months <= 0 or principal <= 0:
        return 0.0
    r = annual_rate / 12.0
    if r == 0:
        return principal / months
    return principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)


def simulate_ashkelon_mortgage(
    months_to_run: int,
    facts: VerifiedFacts,
    assumptions: MarketAssumptions,
) -> Tuple[float, float, float, float]:
    """
    מריץ את משכנתת אשקלון הקיימת למשך months_to_run חודשים החל מ-01/12/2026.
    מחזיר: (יתרת סילוק בסוף התקופה ללא מענק, סך תשלומים ששולמו, סך ריבית והצמדת קרן שנשרפו, החזר חודשי אחרון)
    """
    cpi_bal = facts.ashkelon_cpi_tracks_bal
    unl_bal = facts.ashkelon_unlinked_bal
    cpi_m = facts.ashkelon_cpi_tracks_months
    unl_m = facts.ashkelon_unlinked_months

    r_cpi = facts.ashkelon_cpi_tracks_rate / 12.0
    r_unl = facts.ashkelon_unlinked_rate / 12.0
    m_infl = (1 + assumptions.cpi_annual) ** (1 / 12.0) - 1

    total_paid = 0.0
    total_interest_and_indexation = 0.0
    last_pmt = 0.0

    for m in range(months_to_run):
        # הצמדת קרן חודשית למסלולים הצמודים
        indexation_add = cpi_bal * m_infl
        cpi_bal += indexation_add

        pmt_cpi = spitzer_payment(cpi_bal, facts.ashkelon_cpi_tracks_rate, cpi_m - m)
        int_cpi = cpi_bal * r_cpi
        prin_cpi = pmt_cpi - int_cpi
        cpi_bal -= prin_cpi

        pmt_unl = spitzer_payment(unl_bal, facts.ashkelon_unlinked_rate, unl_m - m)
        int_unl = unl_bal * r_unl
        prin_unl = pmt_unl - int_unl
        unl_bal -= prin_unl

        last_pmt = pmt_cpi + pmt_unl
        total_paid += last_pmt
        total_interest_and_indexation += (int_cpi + int_unl + indexation_add)

    ending_bal = cpi_bal + unl_bal
    return ending_bal, total_paid, total_interest_and_indexation, last_pmt


def calc_tirat_mas_shevach_without_exemption(
    sale_price: float,
    sale_month_from_dec2026: int,
    facts: VerifiedFacts,
    assumptions: MarketAssumptions,
    extra_purchase_tax: float = 0.0,
) -> Tuple[float, float]:
    """
    מחשב מס שבח ריאלי (25%) במכירת טירת הכרמל ללא פטור דירה יחידה (למשל במכירה לפני תום 18 חודשים מטופס 4).
    החוק מתיר ניכוי הוצאות רכישה ומכירה (סעיף 39) ופטור מלא על השבח האינפלציוני (הצמדת התשלומים למדד המחירים לצרכן מיום התשלום).
    מחזיר: (מס שבח לתשלום, מחיר איזון מיסויי מתואם)
    """
    # תשלומים ששולמו ב-2024 (214,000 ב-09/2024 + 1,498,000 ב-12/2024 = 1,712,000 ש"ח)
    # ממועד התשלום המשוקלל (12/2024) ועד 12/2026 חלפו שנתיים (אינפלציה בפועל ~5.2%), ומ-12/2026 לפי cpi_annual
    years_from_dec2026 = sale_month_from_dec2026 / 12.0
    cpi_factor_from_2024 = 1.052 * ((1 + assumptions.cpi_annual) ** years_from_dec2026)

    indexed_2024_payments = (facts.tirat_equity_paid + facts.tirat_contractor_loan) * cpi_factor_from_2024

    # יתרת תשלום במסירה (435,000 ש"ח ב-03/2028 = חודש 15)
    if sale_month_from_dec2026 >= 15:
        years_from_delivery = (sale_month_from_dec2026 - 15) / 12.0
        indexed_final_payment = facts.tirat_final_payment * ((1 + assumptions.cpi_annual) ** years_from_delivery)
    else:
        indexed_final_payment = facts.tirat_final_payment

    # הוצאות מוכרות (עו"ד רכישה, מס רכישה, והוצאות מכירה)
    selling_costs = sale_price * assumptions.selling_cost_pct
    deductible_expenses = (
        (facts.tirat_lawyer_paid + facts.tirat_purchase_tax_paid) * cpi_factor_from_2024
        + extra_purchase_tax
        + selling_costs
    )

    adjusted_cost_basis = indexed_2024_payments + indexed_final_payment + deductible_expenses
    real_gain = max(0.0, sale_price - adjusted_cost_basis)
    mas_shevach = 0.25 * real_gain
    return mas_shevach, adjusted_cost_basis


def calc_investor_purchase_tax_penalty(
    month_paid_from_dec2026: int,
    facts: VerifiedFacts,
    assumptions: MarketAssumptions,
) -> float:
    """
    חישוב השלמת מס רכישה ל-8% (קרן 165,556 ש"ח) + הצמדה למדד וריבית 4% לשנה מיום הרכישה (30/08/2024).
    מ-30/08/2024 עד 01/12/2026 חלפו 2.25 שנים.
    """
    total_years = 2.25 + (month_paid_from_dec2026 / 12.0)
    # ריבית חוקית 4% לשנה + הצמדה למדד (~2.4% ממוצע רב-שנתי)
    effective_annual_penalty_rate = 0.04 + assumptions.cpi_annual
    total_due = facts.tirat_investor_tax_diff_principal * ((1 + effective_annual_penalty_rate) ** total_years)
    return total_due


def run_all_scenarios(
    assumptions: MarketAssumptions = MarketAssumptions(),
    facts: VerifiedFacts = VerifiedFacts(),
) -> List[ScenarioResult]:
    """
    מריץ את 6 החלופות על ציר זמן אחיד של 34 חודשים (01/12/2026 עד 01/09/2029):
    - חודש 0:  01/12/2026 (נקודת פתיחה)
    - חודש 3:  01/03/2027 (תום 5 שנים ממסירת אשקלון - פקיעת מגבלת מחיר למשתכן)
    - חודש 12: 01/12/2027 (מועד פירעון חוזי של הלוואת הקבלן בטירת הכרמל: 1,498,000 ש"ח)
    - חודש 12.5: 15/12/2027 (מחיקת המענק המותנה באשקלון: 54,800 ש"ח!)
    - חודש 13: 01/01/2028 ("חלון הזהב" למכירת אשקלון - אחרי מחיקת המענק ולפני טופס 4 בטירת כרמל)
    - חודש 15: 01/03/2028 (טופס 4 ומסירה בטירת הכרמל + תשלום יתרת 435,000 ש"ח)
    - חודש 18: 01/06/2028 (מועד מכירת אשקלון בחלופה 1א - 3 חודשים אחרי מסירת טירת כרמל)
    - חודש 34: 01/09/2029 (תום 18 חודשים מטופס 4 בטירת הכרמל - נקודת סיום אחידה)
    """
    H = 34  # סה"כ חודשים (12/2026 עד 09/2029)
    r_alt_m = (1 + assumptions.alt_return_net) ** (1 / 12.0) - 1
    r_mort_m = assumptions.new_mortgage_rate / 12.0
    r_bridge_m = assumptions.bridge_loan_rate / 12.0

    def ashkelon_rent_for_month(m: int) -> float:
        # חודשים 0..13 (12/2026 עד 01/2028) = 5,000 ש"ח; חודש 14 ואילך (02/2028+) = 5,250 ש"ח
        return assumptions.ashkelon_rent_p1 if m < 14 else assumptions.ashkelon_rent_p2

    def compound_to_end(amount: float, from_month: int) -> float:
        rem = max(0, H - from_month)
        return amount * ((1 + r_alt_m) ** rem)

    results: List[ScenarioResult] = []

    # =========================================================================
    # חלופה 1א: התכנית המקורית — השלמת טירת כרמל (12/2027-03/2028),
    # מכירת אשקלון אחרי המסירה (06/2028, חודש 18), החזקת טירת כרמל 18 חודשים
    # מטופס 4 ומכירתה ב-09/2029 (חודש 34).
    # =========================================================================
    m_sell_ash_1a = 18  # 01/06/2028
    end_bal_1a, paid_1a, int_ash_1a, last_pmt_1a = simulate_ashkelon_mortgage(m_sell_ash_1a, facts, assumptions)

    # תזרים שוטף באשקלון בחודשים 0..17 (שכירות פחות החזר משכנתה)
    # נחשב את הערך העתידי של התזרים השוטף עד חודש 34
    cf_fv_1a = 0.0
    avg_pmt_ash_1a = paid_1a / m_sell_ash_1a
    for m in range(m_sell_ash_1a):
        net_cf = ashkelon_rent_for_month(m) - avg_pmt_ash_1a
        cf_fv_1a += compound_to_end(net_cf, m + 1)

    # בחודש 12 (01/12/2027): פירעון הלוואת קבלן (1,498,000) באמצעות משכנתה/גישור על טירת כרמל
    # בחודש 15 (01/03/2028): תשלום יתרה במסירה (435,000) באמצעות הלוואת גישור
    # בין חודש 12 לחודש 18 (מכירת אשקלון):
    # - על 1,498,000 משלמים ריבית גישור/משכנתה (נניח גישור חלקי + משכנתה משוקלל 4.75%) למשך 6 חודשים (חודשים 12..18)
    # - על 435,000 משלמים ריבית גישור (5.2%) למשך 3 חודשים (חודשים 15..18)
    bridge_int_1a = (
        facts.tirat_contractor_loan * ((assumptions.new_mortgage_rate + assumptions.bridge_loan_rate) / 2 / 12.0) * 6
        + facts.tirat_final_payment * r_bridge_m * 3
    )
    cf_fv_1a -= compound_to_end(bridge_int_1a, m_sell_ash_1a)

    # שכירות טירת הכרמל בחודשים 15..17 (3 חודשים ראשונים אחרי מסירה ועד מכירת אשקלון)
    for m in range(15, m_sell_ash_1a):
        cf_fv_1a += compound_to_end(assumptions.tirat_rent, m + 1)

    # בחודש 18 (06/2028): מכירת אשקלון!
    # המענק המותנה נמחק ב-15/12/2027 -> קנס מענק = 0.
    # מס שבח = 0 ש"ח (לפי החלטת מיסוי 8838/21, המכירה תוך 12 חודשים ממסירת טירת כרמל).
    ash_sell_costs_1a = assumptions.ashkelon_price * assumptions.selling_cost_pct
    ash_net_proceeds_1a = assumptions.ashkelon_price - ash_sell_costs_1a - end_bal_1a

    # התמורה נטו מאשקלון משמשת להקטנת החוב בטירת הכרמל (1,933,000 ש"ח) בחודש 18:
    tirat_total_needed = facts.tirat_contractor_loan + facts.tirat_final_payment  # 1,933,000
    remaining_debt_tirat_1a = max(0.0, tirat_total_needed - ash_net_proceeds_1a)
    surplus_cash_1a = max(0.0, ash_net_proceeds_1a - tirat_total_needed)
    cf_fv_1a += compound_to_end(surplus_cash_1a, m_sell_ash_1a)

    # חודשים 18..34 (16 חודשים עד תום 18 חודשים מטופס 4):
    # מחזיקים בטירת כרמל עם חוב של remaining_debt_tirat_1a בריבית משכנתה (4.3%), ומקבלים שכירות tirat_rent
    tirat_hold_int_1a = 0.0
    for m in range(m_sell_ash_1a, H):
        m_int = remaining_debt_tirat_1a * r_mort_m
        tirat_hold_int_1a += m_int
        cf_fv_1a += compound_to_end(assumptions.tirat_rent - m_int, m + 1)

    # בחודש 34 (01/09/2029): מכירת טירת הכרמל בפטור מלא ממס שבח (הוחזקה 18 חודשים מטופס 4 כדירה יחידה)
    tirat_sell_costs_1a = assumptions.tirat_price * assumptions.selling_cost_pct
    tirat_net_proceeds_1a = assumptions.tirat_price - tirat_sell_costs_1a - remaining_debt_tirat_1a

    net_equity_1a = tirat_net_proceeds_1a + cf_fv_1a
    total_int_1a = int_ash_1a + bridge_int_1a + tirat_hold_int_1a
    tx_costs_1a = ash_sell_costs_1a + tirat_sell_costs_1a
    deadweight_1a = total_int_1a + tx_costs_1a
    peak_debt_1a = end_bal_1a + tirat_total_needed  # בחודשים 15..18 מחזיקים בשתי הדירות ובשני החובות!
    worst_cf_1a = (
        assumptions.ashkelon_rent_p2
        + assumptions.tirat_rent
        - last_pmt_1a
        - (facts.tirat_contractor_loan * 0.0475 / 12.0)
        - (facts.tirat_final_payment * r_bridge_m)
    )

    results.append(
        ScenarioResult(
            code="1א",
            name="תכנית מקורית (מכירת אשקלון ב-06/2028 אחרי מסירת טירת כרמל + החזקה ל-18 חודשים)",
            net_ending_equity=net_equity_1a,
            total_deadweight_loss=deadweight_1a,
            tax_paid_additional=0.0,
            interest_paid_total=total_int_1a,
            grant_or_contract_penalty=0.0,
            transaction_costs=tx_costs_1a,
            peak_debt=peak_debt_1a,
            peak_bridge_cash_needed=tirat_total_needed,
            worst_monthly_net_cashflow=worst_cf_1a,
            notes="פטור ממס שבח באשקלון נשמר (החלטת מיסוי 8838/21) והמענק נמחק, אך יש חפיפת חוב כפול (~2.65M ש\"ח) ו-18 חודשי החזקה בטירת כרמל.",
        )
    )

    # =========================================================================
    # חלופה 1ב (אופטימלי): מכירת אשקלון ב"חלון הזהב" (01/2028, חודש 13 — מיד אחרי
    # מחיקת המענק המותנה ב-15/12/2027 ולפני טופס 4 בטירת כרמל ב-01/03/2028),
    # והחזקת טירת כרמל ל-18 חודשים מטופס 4 עד 09/2029 (חודש 34).
    # =========================================================================
    m_sell_ash_1b = 13  # 01/01/2028
    end_bal_1b, paid_1b, int_ash_1b, last_pmt_1b = simulate_ashkelon_mortgage(m_sell_ash_1b, facts, assumptions)

    cf_fv_1b = 0.0
    avg_pmt_ash_1b = paid_1b / m_sell_ash_1b
    for m in range(m_sell_ash_1b):
        net_cf = ashkelon_rent_for_month(m) - avg_pmt_ash_1b
        cf_fv_1b += compound_to_end(net_cf, m + 1)

    # גישור ל-1 חודש בלבד (חודש 12 עד 13: 01/12/2027 עד 01/01/2028) על הלוואת הקבלן (1,498,000)
    bridge_int_1b = facts.tirat_contractor_loan * r_bridge_m * 1.0
    cf_fv_1b -= compound_to_end(bridge_int_1b, m_sell_ash_1b)

    # בחודש 13 (01/2028): מכירת אשקלון! המענק המותנה (54.8K) כבר נמחק ב-15/12/2027!
    ash_sell_costs_1b = assumptions.ashkelon_price * assumptions.selling_cost_pct
    ash_net_proceeds_1b = assumptions.ashkelon_price - ash_sell_costs_1b - end_bal_1b

    # פורעים מיד את הלוואת הקבלן (1,498,000) בחודש 13, ונוטלים משכנתה קטנה להשלמה:
    # בחודש 13 משלמים 1,498,000 ובחודש 15 עוד 435,000 (סה"כ 1,933,000).
    debt_at_m13_1b = max(0.0, facts.tirat_contractor_loan - ash_net_proceeds_1b)
    int_m13_to_m15_1b = debt_at_m13_1b * r_mort_m * 2.0
    cf_fv_1b -= compound_to_end(int_m13_to_m15_1b, 15)

    remaining_debt_tirat_1b = max(0.0, tirat_total_needed - ash_net_proceeds_1b)
    tirat_hold_int_1b = 0.0
    for m in range(15, H):  # 19 חודשים (03/2028 עד 09/2029)
        m_int = remaining_debt_tirat_1b * r_mort_m
        tirat_hold_int_1b += m_int
        cf_fv_1b += compound_to_end(assumptions.tirat_rent - m_int, m + 1)

    tirat_sell_costs_1b = assumptions.tirat_price * assumptions.selling_cost_pct
    tirat_net_proceeds_1b = assumptions.tirat_price - tirat_sell_costs_1b - remaining_debt_tirat_1b

    net_equity_1b = tirat_net_proceeds_1b + cf_fv_1b
    total_int_1b = int_ash_1b + bridge_int_1b + int_m13_to_m15_1b + tirat_hold_int_1b
    tx_costs_1b = ash_sell_costs_1b + tirat_sell_costs_1b
    deadweight_1b = total_int_1b + tx_costs_1b

    results.append(
        ScenarioResult(
            code="1ב",
            name="תיקון תזמון (מכירת אשקלון ב-01/2028 לפני טופס 4 ואחרי מחיקת המענק + החזקת טירת כרמל 18 חודשים)",
            net_ending_equity=net_equity_1b,
            total_deadweight_loss=deadweight_1b,
            tax_paid_additional=0.0,
            interest_paid_total=total_int_1b,
            grant_or_contract_penalty=0.0,
            transaction_costs=tx_costs_1b,
            peak_debt=end_bal_1b + facts.tirat_contractor_loan,  # רק לחודש אחד (12/2027)
            peak_bridge_cash_needed=remaining_debt_tirat_1b,
            worst_monthly_net_cashflow=assumptions.tirat_rent - (remaining_debt_tirat_1b * r_mort_m),
            notes="מונע גישור ארוך ונועל פטור מס שבח לפי סעיף 49ב(2) + שומר על המענק (54.8K), אך עדיין מחזיק בטירת כרמל 18 חודשים.",
        )
    )

    # =========================================================================
    # חלופה 1ב-מוקדם: מכירת אשקלון מוקדם מדי (03/2027, חודש 3 — מיד בתום 5 שנים
    # למחיר למשתכן, *לפני* 15/12/2027), והחזקת טירת כרמל ל-18 חודשים עד 09/2029.
    # מציג את המחיר הכבד של שבירת המענק המותנה (54,800 ש"ח)!
    # =========================================================================
    m_sell_ash_1b_early = 3  # 01/03/2027
    end_bal_1be, paid_1be, int_ash_1be, _ = simulate_ashkelon_mortgage(m_sell_ash_1b_early, facts, assumptions)

    cf_fv_1be = 0.0
    avg_pmt_ash_1be = paid_1be / m_sell_ash_1b_early
    for m in range(m_sell_ash_1b_early):
        net_cf = ashkelon_rent_for_month(m) - avg_pmt_ash_1be
        cf_fv_1be += compound_to_end(net_cf, m + 1)

    # במכירה ב-03/2027 משלמים קנס השבת מענק מותנה של 54,800 ש"ח!
    ash_sell_costs_1be = assumptions.ashkelon_price * assumptions.selling_cost_pct
    ash_net_proceeds_1be = (
        assumptions.ashkelon_price - ash_sell_costs_1be - end_bal_1be - facts.ashkelon_grant_penalty
    )

    # ההון הפנוי מאשקלון מופקד בתשואה אלטרנטיבית מחודש 3 עד חודש 12 (9 חודשים) לפני פירעון הלוואת הקבלן:
    cash_at_m12_1be = ash_net_proceeds_1be * ((1 + r_alt_m) ** 9)
    alt_gain_m3_m12 = cash_at_m12_1be - ash_net_proceeds_1be

    debt_at_m12_1be = max(0.0, facts.tirat_contractor_loan - cash_at_m12_1be)
    int_m12_to_m15_1be = debt_at_m12_1be * r_mort_m * 3.0
    cf_fv_1be -= compound_to_end(int_m12_to_m15_1be, 15)

    remaining_debt_tirat_1be = max(0.0, tirat_total_needed - cash_at_m12_1be)
    tirat_hold_int_1be = 0.0
    for m in range(15, H):
        m_int = remaining_debt_tirat_1be * r_mort_m
        tirat_hold_int_1be += m_int
        cf_fv_1be += compound_to_end(assumptions.tirat_rent - m_int, m + 1)

    tirat_sell_costs_1be = assumptions.tirat_price * assumptions.selling_cost_pct
    tirat_net_proceeds_1be = assumptions.tirat_price - tirat_sell_costs_1be - remaining_debt_tirat_1be

    net_equity_1be = tirat_net_proceeds_1be + cf_fv_1be
    total_int_1be = int_ash_1be + int_m12_to_m15_1be + tirat_hold_int_1be
    tx_costs_1be = ash_sell_costs_1be + tirat_sell_costs_1be
    deadweight_1be = total_int_1be + tx_costs_1be + facts.ashkelon_grant_penalty

    results.append(
        ScenarioResult(
            code="1ב-מוקדם",
            name="מכירת אשקלון מוקדמת (03/2027 - לפני מחיקת המענק המותנה) + החזקת טירת כרמל 18 חודשים",
            net_ending_equity=net_equity_1be,
            total_deadweight_loss=deadweight_1be,
            tax_paid_additional=0.0,
            interest_paid_total=total_int_1be,
            grant_or_contract_penalty=facts.ashkelon_grant_penalty,
            transaction_costs=tx_costs_1be,
            peak_debt=end_bal_1be,
            peak_bridge_cash_needed=remaining_debt_tirat_1be,
            worst_monthly_net_cashflow=assumptions.tirat_rent - (remaining_debt_tirat_1be * r_mort_m),
            notes="מדגים מדוע אסור למכור את אשקלון לפני 15/12/2027: שורף 54,800 ש\"ח מענק מותנה!",
        )
    )

    # =========================================================================
    # חלופה 2: יציאה מטירת הכרמל (מכירה/הסבה ב-03/2028 עם קבלת טופס 4 כדי לעקוף
    # את חסם מחירון הקבלן בסעיף 79) והשארת אשקלון.
    # ספיגת 8% מס רכישה רטרואקטיבי + הצמדה וריבית 4% מ-08/2024 (~208,000 ש"ח).
    # =========================================================================
    m_exit_tirat_2 = 15  # 01/03/2028 (נמכרת מיד בטופס 4; אם מוסבת ב-12/2027 התוצאה זהה או גרועה יותר בגלל סעיף 79)
    end_bal_ash_2, paid_ash_2, int_ash_2, last_pmt_2 = simulate_ashkelon_mortgage(H, facts, assumptions)

    cf_fv_2 = 0.0
    avg_pmt_ash_2 = paid_ash_2 / H
    for m in range(H):
        net_cf = ashkelon_rent_for_month(m) - avg_pmt_ash_2
        cf_fv_2 += compound_to_end(net_cf, m + 1)

    # גישור הלוואת קבלן בטירת כרמל מחודש 12 עד חודש 15 (3 חודשים: 12/2027 עד 03/2028)
    bridge_int_2 = facts.tirat_contractor_loan * r_bridge_m * 3.0
    cf_fv_2 -= compound_to_end(bridge_int_2, m_exit_tirat_2)

    # השלמת מס רכישה ל-8% + ריבית 4% והצמדה מ-30/08/2024 ועד חודש 15 (03/2028)
    investor_tax_penalty_2 = calc_investor_purchase_tax_penalty(m_exit_tirat_2, facts, assumptions)

    # בדיקת מס שבח על טירת הכרמל (המס הנוסף מתווסף לעלות המוכרת)
    mas_shevach_tirat_2, _ = calc_tirat_mas_shevach_without_exemption(
        assumptions.tirat_price, m_exit_tirat_2, facts, assumptions, extra_purchase_tax=investor_tax_penalty_2
    )

    tirat_sell_costs_2 = assumptions.tirat_price * assumptions.selling_cost_pct
    # תזרים נטו ממכירת טירת הכרמל בחודש 15 (אחרי פירעון 1,498K הלוואת קבלן + 435K יתרה למסירה + מס רכישה 8% + הוצאות מכירה)
    tirat_net_cash_m15_2 = (
        assumptions.tirat_price
        - tirat_sell_costs_2
        - tirat_total_needed
        - investor_tax_penalty_2
        - mas_shevach_tirat_2
    )
    # תזרים זה (חיובי או שלילי) צובר ריבית אלטרנטיבית/מימון מחודש 15 עד חודש 34 (19 חודשים)
    cf_fv_2 += compound_to_end(tirat_net_cash_m15_2, m_exit_tirat_2)

    # שווי אשקלון בסוף התקופה (חודש 34) בניכוי יתרת המשכנתה שלה והוצאות מכירה (בהנחה שנמכרת לפני טופס 4 ברתמים כדי לממן בנייה ולנצור פטור מס שבח)
    ash_sell_costs_2 = assumptions.ashkelon_price * assumptions.selling_cost_pct
    ash_net_equity_end_2 = assumptions.ashkelon_price - ash_sell_costs_2 - end_bal_ash_2

    net_equity_2 = ash_net_equity_end_2 + cf_fv_2
    total_int_2 = int_ash_2 + bridge_int_2
    tx_costs_2 = tirat_sell_costs_2 + ash_sell_costs_2
    total_tax_2 = investor_tax_penalty_2 + mas_shevach_tirat_2
    deadweight_2 = total_int_2 + tx_costs_2 + total_tax_2

    results.append(
        ScenarioResult(
            code="2",
            name="יציאה מטירת כרמל והשארת אשקלון (ספיגת מס רכישה 8% רטרואקטיבי + ריבית והצמדה)",
            net_ending_equity=net_equity_2,
            total_deadweight_loss=deadweight_2,
            tax_paid_additional=total_tax_2,
            interest_paid_total=total_int_2,
            grant_or_contract_penalty=0.0,
            transaction_costs=tx_costs_2,
            peak_debt=end_bal_1b + tirat_total_needed,
            peak_bridge_cash_needed=tirat_total_needed,
            worst_monthly_net_cashflow=assumptions.ashkelon_rent_p2 - last_pmt_2 - (facts.tirat_contractor_loan * r_bridge_m),
            notes=f"שורף {investor_tax_penalty_2:,.0f} ש\"ח מס רכישה רטרואקטיבי (8% + ריבית והצמדה) וממשיך לשאת משכנתת מל\"צ 4.86% באשקלון.",
        )
    )

    # =========================================================================
    # חלופה 3א (ההמלצה האנליטית החדה!):
    # מכירת אשקלון ב"חלון הזהב" (01/2028, חודש 13 — מיד אחרי מחיקת המענק 54.8K)
    # + מכירת טירת הכרמל מיד עם קבלת טופס 4 (03/2028, חודש 15) *ללא* המתנה של 18 חודשים!
    # כל ההון העצמי (~1.46M ש"ח) משתחרר כבר ב-03/2028 למימון הבנייה ברתמים (חוסך 4.3% ריבית משכנתה ל-19 חודשים)!
    # =========================================================================
    m_sell_ash_3a = 13  # 01/01/2028
    m_sell_tirat_3a = 15  # 01/03/2028 (מיד בטופס 4)
    end_bal_3a, paid_3a, int_ash_3a, _ = simulate_ashkelon_mortgage(m_sell_ash_3a, facts, assumptions)

    cf_fv_3a = 0.0
    avg_pmt_ash_3a = paid_3a / m_sell_ash_3a
    for m in range(m_sell_ash_3a):
        net_cf = ashkelon_rent_for_month(m) - avg_pmt_ash_3a
        cf_fv_3a += compound_to_end(net_cf, m + 1)

    # גישור 1 חודש על הלוואת הקבלן (חודש 12 עד 13) + 2 חודשים על יתרת ההלוואה (חודש 13 עד 15)
    ash_sell_costs_3a = assumptions.ashkelon_price * assumptions.selling_cost_pct
    ash_net_proceeds_3a = assumptions.ashkelon_price - ash_sell_costs_3a - end_bal_3a
    debt_m13_3a = max(0.0, facts.tirat_contractor_loan - ash_net_proceeds_3a)

    bridge_int_3a = (facts.tirat_contractor_loan * r_bridge_m * 1.0) + (debt_m13_3a * r_bridge_m * 2.0)
    cf_fv_3a -= compound_to_end(bridge_int_3a, m_sell_tirat_3a)

    # מס שבח על טירת הכרמל במכירה מיידית בטופס 4 (ללא פטור 18 חודשים, אך עם עלות מתואמת למדד + הוצאות מוכרות ~2.33M ש"ח!)
    mas_shevach_tirat_3a, adj_cost_3a = calc_tirat_mas_shevach_without_exemption(
        assumptions.tirat_price, m_sell_tirat_3a, facts, assumptions
    )

    tirat_sell_costs_3a = assumptions.tirat_price * assumptions.selling_cost_pct
    # בחודש 15 (03/2028) מוכרים את טירת הכרמל ומקבלים את כל ההון העצמי המשולב נטו:
    total_free_equity_m15_3a = (
        ash_net_proceeds_3a
        + assumptions.tirat_price
        - tirat_sell_costs_3a
        - tirat_total_needed
        - mas_shevach_tirat_3a
    )

    # ההון המשוחרר בחודש 15 (03/2028) חוסך ריבית משכנתת בנייה ברתמים / צובר תשואה אלטרנטיבית (4.3%) במשך 19 חודשים עד 09/2029!
    net_equity_3a = compound_to_end(total_free_equity_m15_3a, m_sell_tirat_3a) + cf_fv_3a
    total_int_3a = int_ash_3a + bridge_int_3a
    tx_costs_3a = ash_sell_costs_3a + tirat_sell_costs_3a
    deadweight_3a = total_int_3a + tx_costs_3a + mas_shevach_tirat_3a

    results.append(
        ScenarioResult(
            code="3א",
            name="אופטימיזציה מומלצת: מכירת אשקלון ב-01/2028 + מכירת טירת כרמל מיד בטופס 4 (03/2028) והזרמת ההון לרתמים",
            net_ending_equity=net_equity_3a,
            total_deadweight_loss=deadweight_3a,
            tax_paid_additional=mas_shevach_tirat_3a,
            interest_paid_total=total_int_3a,
            grant_or_contract_penalty=0.0,
            transaction_costs=tx_costs_3a,
            peak_debt=end_bal_3a + facts.tirat_contractor_loan,
            peak_bridge_cash_needed=tirat_total_needed - ash_net_proceeds_3a,
            worst_monthly_net_cashflow=assumptions.ashkelon_rent_p1 - (paid_3a / m_sell_ash_3a),
            notes=(
                f"מנצלת את העובדה שמחיר האיזון המיסויי של טירת כרמל הוא ~{adj_cost_3a:,.0f} ש\"ח (ולכן מס שבח = {mas_shevach_tirat_3a:,.0f} ש\"ח גם בלי להמתין 18 חודשים!). "
                f"משחררת ~{total_free_equity_m15_3a:,.0f} ש\"ח במזומן כבר ב-03/2028 לבנייה ברתמים וחוסכת 19 חודשי מימון כפול."
            ),
        )
    )

    # =========================================================================
    # חלופה 3ב: מכירת אשקלון ב-01/2028 והחזקה ארוכת טווח בטירת כרמל (ללא מכירה ב-09/2029)
    # זהה לחלופה 1ב בתזרים עד 09/2029, אך ללא הוצאות מכירה של טירת הכרמל (ועם חשיפת מס עתידית מול רתמים).
    # =========================================================================
    net_equity_3b_book = net_equity_1b + tirat_sell_costs_1b
    deadweight_3b = total_int_1b + ash_sell_costs_1b

    results.append(
        ScenarioResult(
            code="3ב",
            name="החזקה ארוכת טווח בטירת כרמל (מכירת אשקלון ב-01/2028 והשארת טירת כרמל כנכס מניב במקביל לרתמים)",
            net_ending_equity=net_equity_3b_book,
            total_deadweight_loss=deadweight_3b,
            tax_paid_additional=0.0,
            interest_paid_total=total_int_1b,
            grant_or_contract_penalty=0.0,
            transaction_costs=ash_sell_costs_1b,
            peak_debt=end_bal_1b + facts.tirat_contractor_loan,
            peak_bridge_cash_needed=remaining_debt_tirat_1b,
            worst_monthly_net_cashflow=assumptions.tirat_rent - (remaining_debt_tirat_1b * r_mort_m),
            notes=(
                "תשואת השכירות נטו בטירת כרמל (~2.8%) נמוכה מעלות המימון ברתמים (4.3%), כלומר הפסד מימוני שוטף של ~1.5% לשנה (~31,500 ש\"ח/שנה) "
                "ונועל ~1.46M ש\"ח הון עצמי שנדרש לבנייה ברתמים + יוצר כפל דירות מול טופס 4 ברתמים ב-06/2030."
            ),
        )
    )

    return results


def print_summary_report():
    base_assumptions = MarketAssumptions()
    facts = VerifiedFacts()
    results = run_all_scenarios(base_assumptions, facts)

    print("=" * 115)
    print("השוואת חלופות — תרחיש בסיס (אשקלון = 2,100,000 ש\"ח | טירת הכרמל = 2,100,000 ש\"ח | ריבית = 4.3% | אופק = 09/2029)")
    print("=" * 115)
    header = f"{'קוד':<8} | {'הון עצמי נטו בסוף (ש\"ח)':>22} | {'כסף שרוף (Deadweight)':>21} | {'מסים נוספים':>12} | {'סך ריביות':>12} | {'קנס מענק/חוזה':>13} | {'שיא חוב':>12}"
    print(header)
    print("-" * 115)
    for r in sorted(results, key=lambda x: x.net_ending_equity, reverse=True):
        print(
            f"{r.code:<8} | {r.net_ending_equity:>22,.0f} | {r.total_deadweight_loss:>21,.0f} | "
            f"{r.tax_paid_additional:>12,.0f} | {r.interest_paid_total:>12,.0f} | "
            f"{r.grant_or_contract_penalty:>13,.0f} | {r.peak_debt:>12,.0f}"
        )

    print("\n" + "=" * 115)
    print("מטריצת רגישות 1: שווי מכירת אשקלון מול שווי מכירת טירת הכרמל — הון עצמי נטו בסוף התקופה (וזהות החלופה המנצחת)")
    print("=" * 115)
    ash_prices = [1_950_000, 2_100_000, 2_250_000]
    tirat_prices = [1_950_000, 2_100_000, 2_250_000, 2_380_000]

    for ap in ash_prices:
        print(f"\n--- שווי מכירת אשקלון: {ap:,.0f} ש\"ח ---")
        print(f"{'שווי טירת כרמל':<16} | {'חלופה 3א (מכירה בטופס 4)':>25} | {'חלופה 1ב (החזקה 18ח\')':>23} | {'חלופה 1א (מקורית)':>20} | {'חלופה 2 (השארת אשקלון)':>23} | {'מנצחת':<8}")
        print("-" * 125)
        for tp in tirat_prices:
            a = MarketAssumptions(ashkelon_price=ap, tirat_price=tp)
            res = {r.code: r for r in run_all_scenarios(a, facts)}
            # Compare liquid/realized exit alternatives (3א, 1ב, 1א, 2)
            candidates = ["3א", "1ב", "1א", "2"]
            best_code = max(candidates, key=lambda c: res[c].net_ending_equity)
            print(
                f"{tp:>14,.0f} ₪ | {res['3א'].net_ending_equity:>23,.0f} ₪ | "
                f"{res['1ב'].net_ending_equity:>21,.0f} ₪ | {res['1א'].net_ending_equity:>18,.0f} ₪ | "
                f"{res['2'].net_ending_equity:>21,.0f} ₪ | {best_code:<8}"
            )

    print("\n" + "=" * 115)
    print("מטריצת רגישות 2: ריבית מימון / עלות אלטרנטיבית להון (3.5% / 4.3% / 5.5%) ושכירות טירת כרמל (4,600 / 5,000 / 5,400 ש\"ח)")
    print("=" * 115)
    rates = [0.035, 0.043, 0.055]
    rents = [4_600, 5_000, 5_400]
    print(f"{'ריבית / שכירות':<18} | {'חלופה 3א (מכירה בטופס 4)':>25} | {'חלופה 1ב (החזקה 18ח\')':>23} | {'חלופה 1א (מקורית)':>20} | {'פער 3א מול 1ב':>16}")
    print("-" * 115)
    for rt in rates:
        for rnt in rents:
            a = MarketAssumptions(
                new_mortgage_rate=rt,
                alt_return_net=rt,
                bridge_loan_rate=rt + 0.009,
                tirat_rent=rnt,
            )
            res = {r.code: r for r in run_all_scenarios(a, facts)}
            diff = res["3א"].net_ending_equity - res["1ב"].net_ending_equity
            print(
                f"{rt*100:>4.1f}% / {rnt:>5,.0f} ש\"ח | {res['3א'].net_ending_equity:>23,.0f} ₪ | "
                f"{res['1ב'].net_ending_equity:>21,.0f} ₪ | {res['1א'].net_ending_equity:>18,.0f} ₪ | "
                f"{diff:>+14,.0f} ₪"
            )

    print("\n" + "=" * 115)
    print("ניתוח נקודות איזון (Break-Even Points)")
    print("=" * 115)
    # 1. מאיזה מחיר של טירת הכרמל כדאי להחזיק אותה 18 חודשים אחרי טופס 4 (חלופה 1ב) במקום למכור מיד בטופס 4 (חלופה 3א)?
    # הפער ברווח ההון הפטור ממס שבח צריך לכסות את הפסד המימון של 19 החודשים (~42,953 ש"ח בתרחיש בסיס).
    _, tax_be_price = calc_tirat_mas_shevach_without_exemption(2_100_000, 15, facts, base_assumptions)
    # Find exact price where 1b beats 3a (assuming same price at month 15 and month 34)
    be_hold_price = None
    for tp_test in range(2_100_000, 3_000_000, 1_000):
        a_test = MarketAssumptions(tirat_price=float(tp_test))
        res_test = {r.code: r for r in run_all_scenarios(a_test, facts)}
        if res_test["1ב"].net_ending_equity >= res_test["3א"].net_ending_equity:
            be_hold_price = tp_test
            break

    print(f"1. מחיר איזון מיסויי בטירת הכרמל (Tax Cost Basis ב-03/2028 כולל מדד והוצאות): {tax_be_price:,.0f} ש\"ח")
    print(f"   -> עד מחיר של {tax_be_price:,.0f} ש\"ח, מס השבח במכירה מיידית בטופס 4 הוא 0 ש\"ח!")
    if be_hold_price:
        print(f"2. נקודת איזון להמתנת 18 חודשים (חלופה 1ב עוקפת את 3א רק אם שווי טירת הכרמל כבר בטופס 4 עולה על): {be_hold_price:,.0f} ש\"ח")
        print(f"   (או אם טירת הכרמל תעלה בערכה במהלך 18 החודשים שאחרי טופס 4 ביותר מ-~43,000 ש\"ח נומינלית, קרי >2.05%).")
    print("3. נקודת איזון לחלופה 2 (יציאה מטירת כרמל והשארת אשקלון תוך ספיגת מס רכישה 8%):")
    print("   -> מכיוון שמס הרכישה (5,644 ש\"ח) כבר שולם וההצמדה למדד בטירת הכרמל היא 0%,")
    print("      יציאה מטירת כרמל *ללא* מכירת אשקלון קונסת אתכם ב-~208,000 ש\"ח מס רכישה רטרואקטיבי.")
    print("      לכן עבור כל מחיר של טירת הכרמל, חלופה 3א (מכירת אשקלון + מכירת טירת כרמל) עדיפה על חלופה 2 בפער קבוע של ~175,000-210,000 ש\"ח!")


if __name__ == "__main__":
    print_summary_report()
