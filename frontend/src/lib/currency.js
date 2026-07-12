// Currency formatting helpers used across the dashboard.
// Prefers Intl.NumberFormat for accurate localised symbols/positions.

const LOCALE_BY_CURRENCY = {
  USD: "en-US",
  EUR: "en-IE",
  GBP: "en-GB",
  INR: "en-IN",
  JPY: "ja-JP",
  CNY: "zh-CN",
  KRW: "ko-KR",
  AUD: "en-AU",
  CAD: "en-CA",
  CHF: "de-CH",
  SGD: "en-SG",
  AED: "en-AE",
  BRL: "pt-BR",
  MXN: "es-MX",
  SEK: "sv-SE",
  NOK: "nb-NO",
  ZAR: "en-ZA",
};

export function formatCurrency(value, currency = "USD", opts = {}) {
  const num = Number(value) || 0;
  const locale = LOCALE_BY_CURRENCY[currency] || "en-US";
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      maximumFractionDigits: opts.maxFractionDigits ?? (num >= 1000 ? 1 : 2),
      minimumFractionDigits: opts.minFractionDigits ?? 0,
      notation: opts.compact && num >= 1000 ? "compact" : "standard",
    }).format(num);
  } catch {
    return `${currency} ${num.toLocaleString()}`;
  }
}

export function currencySymbol(currency = "USD") {
  try {
    const parts = new Intl.NumberFormat(
      LOCALE_BY_CURRENCY[currency] || "en-US",
      { style: "currency", currency, maximumFractionDigits: 0 },
    ).formatToParts(0);
    const sym = parts.find((p) => p.type === "currency");
    return sym?.value || currency;
  } catch {
    return currency;
  }
}
