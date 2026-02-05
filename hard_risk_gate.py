def hard_risk_gate(price, extra_data):
    if price <= 0:
        return False, "價格異常"

    order_strength = extra_data.get("order_strength", "")
    if any(x in order_strength for x in ["大量賣", "急殺", "出貨"]):
        return False, "盤中賣壓過大"

    market = extra_data.get("market_context", "")
    if any(x in market for x in ["系統性風險", "崩跌", "恐慌"]):
        return False, "市場風險過高"

    return True, "風控通過"
