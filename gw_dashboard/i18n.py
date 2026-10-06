"""User-interface text in English and Arabic.

To change a sentence, edit it here. Keep the {placeholders} unchanged.
"""

from __future__ import annotations

LANGUAGES = {"en": "English", "ar": "العربية"}

TEXT: dict[str, dict[str, str]] = {
    "en": {
        "page_title": "Groundwater Analysis – {place}",
        "header": "💧 Agricultural Groundwater Analysis Dashboard",
        "subheader": "{place} · monthly maps, {first} to {last}",
        "control_panel": "Control panel",
        "parameter": "Parameter",
        "parameter_help": "Choose the layer to show on the map",
        "month": "Month",
        "visual_settings": "🎨 Display settings",
        "opacity": "Layer opacity",
        "location_settings": "📍 Map position",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "zoom": "Zoom level",
        "reset_view": "Reset view",
        "interactive_map": "Interactive map",
        "map_hint": "Click anywhere on the coloured layer to see its monthly time series below.",
        "auto_scale": "Colours stretched between the 2nd and 98th percentile of this month; statistics below use all pixels.",
        "fixed_scale": "Colour scale fixed in settings.toml (same for every month).",
        "statistics": "Statistics for {month}",
        "minimum": "Minimum",
        "maximum": "Maximum",
        "mean": "Mean",
        "time_series": "Time series",
        "click_map": "Click a location on the map to see how the value changes over time.",
        "ts_title": "{parameter} at ({lat}, {lon})",
        "no_data_point": "No data at this location – please click inside the coloured area.",
        "download_csv": "⬇️ Download time series (CSV)",
        "date": "Month",
        "value": "Value",
        "legend": "{parameter} ({unit})",
        "selected_month": "Selected month",
        "about": "ℹ️ About this dashboard",
        "about_text": (
            "This dashboard shows monthly groundwater **abstraction** and **recharge** estimates "
            "for {place}, computed with Google Earth Engine from satellite data.\n\n"
            "- 🌍 **Map** – choose a parameter and a month; switch the base map with the layer button.\n"
            "- 📊 **Statistics** – minimum, mean and maximum over the study area for that month.\n"
            "- 📈 **Time series** – click any point to see its full monthly history and download it."
        ),
        "developed_by": "Developed by {org}.",
        "contact_line": "Contact: {contact}",
        "tech_details": "🔧 Technical details",
        "data_folder": "Earth Engine data folder",
        "configured_in": "configured in",
        "available": "Available months",
        "loading": "Loading data from Google Earth Engine…",
        # errors
        "err_settings": "The dashboard settings are not valid.",
        "err_credentials": "Earth Engine credentials are missing or not valid.",
        "err_credentials_help": (
            "If you maintain this app: open the app on share.streamlit.io → ⋮ → **Settings** → "
            "**Secrets**, and paste the service-account key as shown in `.streamlit/secrets.toml.example`."
        ),
        "err_init": "Could not connect to Google Earth Engine.",
        "err_assets": "Could not read the Earth Engine data folder.",
        "err_no_assets": "No images were found in the data folder, or the service account cannot read it.",
        "err_no_param_data": "No months are available for this parameter.",
        "err_map": "Could not draw the map for this month.",
        "err_stats": "Could not calculate statistics.",
        "err_ts": "Could not read the time series for this point.",
        "details": "Details",
    },
    "ar": {
        "page_title": "تحليل المياه الجوفية – {place}",
        "header": "💧 لوحة تحليل المياه الجوفية الزراعية",
        "subheader": "{place} · خرائط شهرية، من {first} إلى {last}",
        "control_panel": "لوحة التحكم",
        "parameter": "المعامل",
        "parameter_help": "اختر الطبقة التي تظهر على الخريطة",
        "month": "الشهر",
        "visual_settings": "🎨 إعدادات العرض",
        "opacity": "شفافية الطبقة",
        "location_settings": "📍 موضع الخريطة",
        "latitude": "خط العرض",
        "longitude": "خط الطول",
        "zoom": "مستوى التكبير",
        "reset_view": "إعادة ضبط العرض",
        "interactive_map": "الخريطة التفاعلية",
        "map_hint": "انقر على أي موقع داخل الطبقة الملونة لعرض السلسلة الزمنية الشهرية أدناه.",
        "auto_scale": "الألوان ممتدة بين المئين الثاني والمئين الثامن والتسعين لهذا الشهر؛ الإحصاءات أدناه تشمل جميع البكسلات.",
        "fixed_scale": "مقياس الألوان ثابت في ملف settings.toml (نفسه لكل الأشهر).",
        "statistics": "إحصاءات شهر {month}",
        "minimum": "الحد الأدنى",
        "maximum": "الحد الأقصى",
        "mean": "المتوسط",
        "time_series": "السلسلة الزمنية",
        "click_map": "انقر على موقع في الخريطة لمعرفة تغير القيمة عبر الزمن.",
        "ts_title": "{parameter} عند ({lat}، {lon})",
        "no_data_point": "لا توجد بيانات في هذا الموقع – يرجى النقر داخل المنطقة الملونة.",
        "download_csv": "⬇️ تنزيل السلسلة الزمنية (CSV)",
        "date": "الشهر",
        "value": "القيمة",
        "legend": "{parameter} ({unit})",
        "selected_month": "الشهر المختار",
        "about": "ℹ️ حول هذه اللوحة",
        "about_text": (
            "تعرض هذه اللوحة تقديرات شهرية **لسحب** المياه الجوفية **وتغذيتها** في {place}، "
            "محسوبة باستخدام Google Earth Engine من بيانات الأقمار الصناعية.\n\n"
            "- 🌍 **الخريطة** – اختر المعامل والشهر، ويمكن تغيير الخريطة الأساسية من زر الطبقات.\n"
            "- 📊 **الإحصاءات** – الحد الأدنى والمتوسط والحد الأقصى لمنطقة الدراسة في ذلك الشهر.\n"
            "- 📈 **السلسلة الزمنية** – انقر على أي نقطة لعرض تاريخها الشهري الكامل وتنزيله."
        ),
        "developed_by": "تطوير: {org}.",
        "contact_line": "للتواصل: {contact}",
        "tech_details": "🔧 تفاصيل تقنية",
        "data_folder": "مجلد بيانات Earth Engine",
        "configured_in": "محدد في",
        "available": "الأشهر المتاحة",
        "loading": "جارٍ تحميل البيانات من Google Earth Engine…",
        "err_settings": "إعدادات اللوحة غير صالحة.",
        "err_credentials": "بيانات اعتماد Earth Engine مفقودة أو غير صالحة.",
        "err_credentials_help": (
            "إذا كنت مسؤولاً عن هذا التطبيق: افتح التطبيق على share.streamlit.io ← ⋮ ← **Settings** ← "
            "**Secrets** والصق مفتاح حساب الخدمة كما في `.streamlit/secrets.toml.example`."
        ),
        "err_init": "تعذر الاتصال بـ Google Earth Engine.",
        "err_assets": "تعذرت قراءة مجلد بيانات Earth Engine.",
        "err_no_assets": "لم يتم العثور على صور في مجلد البيانات، أو أن حساب الخدمة لا يملك صلاحية قراءته.",
        "err_no_param_data": "لا توجد أشهر متاحة لهذا المعامل.",
        "err_map": "تعذر رسم الخريطة لهذا الشهر.",
        "err_stats": "تعذر حساب الإحصاءات.",
        "err_ts": "تعذرت قراءة السلسلة الزمنية لهذه النقطة.",
        "details": "التفاصيل",
    },
}


def tr(lang: str, key: str, **kwargs) -> str:
    """Translated text; falls back to English, then to the key itself."""
    text = TEXT.get(lang, TEXT["en"]).get(key) or TEXT["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text
