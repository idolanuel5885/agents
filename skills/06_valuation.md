# SKILL: עקרונות ושיקולים + נתוני השוואה + שומה

## מה זה
הלב המקצועי של הדוח. מורכב משלושה חלקים בסדר קבוע.

---

# חלק א': עקרונות, גורמים ושיקולים באומדן השווי

## מבנה — ארבעה תתי-חלקים קבועים

### 1. כללי
רשימת נקודות (bullet) המסכמות את מאפייני הנכס:
- מיקום הנכס (עיר + שכונה)
- אופי הסביבה
- שנת בניית הבניין + מספר דירות + קומות
- מאפייני הדירה (חדרים, קומה, כיוון)
- שטח הדירה [+ מרפסת]
- גובה פנים (אם יש נתון חריג)
- מצב היתר
- רמת גמר
- הצמדות (חניה, מחסן)
- כל נתון מיוחד (שכירות לקרוב משפחה, פינוי-בינוי, תמ"א וכו')

### 2. תכנון ורישוי
שלושה bullet קבועים:
- "בהתאם לתכניות בניין עיר שבתוקף החלקה בה ממוקמת הדירה שבנדון מסווגת ביעוד '[ייעוד]'."
- "הדירה שבנדון בנויה בהתאם להיתר בניה משנת [X]."
- "תעודת גמר לבניין ניתנה בשנת [X]." (רק אם בניין חדש / אם יש תעודת גמר)

### 3. מצב משפטי
שלושה bullet קבועים:
- "החלקה בה ממוקמת הדירה שבנדון נרשמה בפנקס הבתים המשותפים, באופן בו כל תת חלקה מהווה יחידה עצמאית מבחינה משפטית."
- "הדירה שבנדון רשומה על שם [בעלי הזכויות]."
- "נכון למועד הביקור, הדירה מושכרת בשכירות חופשית." / "הדירה אינה מושכרת."

הוסף bullet נוסף אם רלוונטי:
- בעלות משותפת: "מאחר וחוות הדעת נערכה לדירה בשלמות, לא הובאה בחשבון הפחתה למושע."
- שכירות לקרוב משפחה: "לאור הקשר בין בעלי הדירה לשוכרת לא הובאה בחשבון הפחתה..."

### 4. עקרונות התחשיב
bullet קבוע:
- "אומדן השווי נערך לנכס שבנדון כחופשי מכל הערה, חוב ושעבוד."
- "הובא בחשבון מצב שוק המקרקעין ומחירי נכסים דומים ורלוונטיים בסביבת הנכס וסביב המועד הקובע לחוות הדעת."

הוסף אם רלוונטי:
- סגירת מרפסות ללא היתר: "בסביבת הנכס נהוג לסגור מרפסות כפי שבוצע בנכס שבנדון ולפיכך הובא בחשבון כי גם נתוני ההשוואה כוללים מרפסות שנסגרו שלא בהתאם להיתר."
- הערת אזהרה פינוי-בינוי: "סקר נתוני ההשוואה כולל דירות מגורים מהחלקה בה ממוקמת הדירה שבנדון, באופן בו פוטנציאל בגין התחדשות עירונית מגולם בנתוני ההשוואה."

---

# חלק ב': נתוני השוואה

## מקורות
- עסקאות שבוצעו: nadlan.gov.il (API)
- מחירי היצע: yad2 / madlan
- כל עסקה: תאריך, כתובת, קומה, שטח, מחיר, מחיר למ"ר

## מבנה טבלת ההשוואה (שדות)
| מספר | כתובת | קומה | חדרים | שטח מ"ר | מרפסת מ"ר | מחיר | ₪/מ"ר אקו' | הערות |

## סוגי נתוני השוואה — לפי סוג הנכס

### דירה ותיקה בסביבה ותיקה
- עסקאות מכירה בסביבה הקרובה, תקופה: שנה-שנתיים אחורה
- משפט פתיחה: "להלן עסקאות מכירה בפועל לדירות מגורים [ותיקות/דומות] בסביבה הקרובה של הנכס שבנדון:"

### דירה חדשה / פנטהאוז
- עסקאות מכירה של דירות דומות בפרויקטים דומים
- לפעמים גם: נתוני היצע (דירות המוצעות למכירה)
- לפעמים שתי טבלאות: פנטהאוז + דירות טיפוסיות

### דירות בחלקה עצמה
- כשיש עסקאות בבניין עצמו — אלה ה-comparable הטוב ביותר
- ציין בכותרת: "להלן עסקאות מכירה בפועל לדירות שהינן חלק מהחלקה בה ממוקם הנכס שבנדון:"

## מקדמי אקוויוולנציה למרפסות (סטנדרטי)
```
עד 50 מ"ר מרפסת   → מקדם 0.5
50-100 מ"ר מרפסת  → מקדם 0.25
מעל 100 מ"ר מרפסת → מקדם 0.1
```
(לגינות: עד 50 מ"ר → 0.4, 50-100 מ"ר → 0.25)

## מפת עסקאות
"מפת מיקומי עסקאות ההשוואה:"
[מיקום לתמונת מפה עם ממוספרים]

## סיכום
"לאור הנתונים שהוצגו לעיל, ובהתחשב במאפייני הנכס שבנדון ובמיקומו נראה כסביר לאמוד [שווי מ"ר אקו' / שווי הדירה] בסך של כ- X ₪ [/ מ"ר אקו']."

---

# חלק ג': שומה

## תחשיב
טבלה:
```
שטח עיקרי   : X מ"ר  × Y ₪/מ"ר  = Z ₪
מרפסת        : X מ"ר  × Y ₪/מ"ר  = Z ₪ (מקדם 0.5)
חניה         : [כלולה בשווי מ"ר / נפרד]
סה"כ         : Z ₪
```
הערת שוליים: "השווי למ"ר אקוי' מגלם את מיקום הדירה בבניין, את רמת הגמר, קיומה של חניה, מצב הדירה וכו'."

## ניסוח השומה הסופית — קבוע
```
בהתבסס על כל האמור לעיל ובמיקומו של הנכס המהווה את תת חלקה X בחלקה מספר Y בגוש Z, ברחוב [כתובת מלאה]:

אומדן שווי הזכויות בנכס שבנדון הינו סביב X,XXX,000 ₪
([סכום במילים] שקלים חדשים) כולל מע"מ.
```

## שווי מימוש מהיר — רק בתקן 19
```
לצורך מימוש מהיר בדרך של מכירה באילוץ, ניתן להעמיד את שווי הנכס על סך של 85% מהשווי הנקוב לעיל.
```

## הצהרות סיום — קבוע בכל דוח
```
הננו מצהירים כי אין לנו עניין אישי עם הנכס שבנדון, בעלי הזכויות בנכס או עם מזמין חוות הדעת.

חוות הדעת נערכה על פי תקנות שמאי המקרקעין (אתיקה מקצועית) התשכ"ו – 1966 ועל פי התקנים המקצועיים של הועדה לתקינה שמאית במועצת שמאי המקרקעין.

שומה זו הוכנה עבור מזמינה ולמטרתה בלבד. אין היא מהווה תחליף לייעוץ משפטי ואין להסתמך עליה לכל מטרה אחרת. השימוש בשומה נאסר על כל צד שלישי שהוא, אשר אינו המזמין ועורך השומה לא יהא אחראי להסתמכות כלשהי כאמור.
```

---

## Generator snippets

<!-- snippet: section_06.heading -->
<!-- character: fixed -->
עקרונות ושיקולים, נתוני השוואה ושומה
<!-- /snippet -->

<!-- snippet: section_06.principles.heading -->
<!-- character: fixed -->
א. עקרונות, גורמים ושיקולים
<!-- /snippet -->

<!-- snippet: section_06.principles.general.title -->
<!-- character: fixed -->
1. כללי
<!-- /snippet -->

<!-- snippet: section_06.principles.general.location -->
<!-- character: semi -->
מיקום הנכס: {address}.
<!-- /snippet -->

<!-- snippet: section_06.principles.general.environment -->
<!-- character: semi -->
אופי הסביבה: {neighborhood} ב{city}.
<!-- /snippet -->

<!-- snippet: section_06.principles.general.building -->
<!-- character: semi -->
שנת בניית הבניין: {build_year}. מספר יחידות הדיור בבניין: {units_count}.
<!-- /snippet -->

<!-- snippet: section_06.principles.general.apartment -->
<!-- character: semi -->
הדירה ממוקמת בקומה ה-{floor_ord}, בת {rooms} חדרים, פונה לכיוון {air}.
<!-- /snippet -->

<!-- snippet: section_06.principles.general.area_no_balcony -->
<!-- character: semi -->
שטח הדירה הבנוי הינו כ-{built_area:.0f} מ"ר.
<!-- /snippet -->

<!-- snippet: section_06.principles.general.area_with_balcony -->
<!-- character: semi -->
שטח הדירה הבנוי הינו כ-{built_area:.0f} מ"ר, ומרפסת בשטח כ-{balcony_area:.0f} מ"ר.
<!-- /snippet -->

<!-- snippet: section_06.principles.general.ceiling -->
<!-- character: semi -->
גובה פנים: כ-{ceiling_height:.1f} מ'.
<!-- /snippet -->

<!-- snippet: section_06.principles.general.permit_normal -->
<!-- character: fixed -->
הדירה בנויה בהתאם להיתר — מצב היתר.
<!-- /snippet -->

<!-- snippet: section_06.principles.general.permit_balcony_unpermitted -->
<!-- character: fixed -->
הדירה בנויה בהתאם להיתר (למעט סגירת המרפסת) — מצב היתר.
<!-- /snippet -->

<!-- snippet: section_06.principles.general.permit_violations -->
<!-- character: fixed -->
נמצאו חריגות בנייה. — מצב היתר.
<!-- /snippet -->

<!-- snippet: section_06.principles.general.finish -->
<!-- character: semi -->
רמת גמר: {level}.
<!-- /snippet -->

<!-- snippet: section_06.principles.general.attachments -->
<!-- character: semi -->
הצמדות: {atts}.
<!-- /snippet -->

<!-- snippet: section_06.principles.general.attachment.parking -->
<!-- character: fixed -->
חניה
<!-- /snippet -->

<!-- snippet: section_06.principles.general.attachment.storage -->
<!-- character: fixed -->
מחסן
<!-- /snippet -->

<!-- snippet: section_06.principles.general.attachment.garden -->
<!-- character: fixed -->
גינה
<!-- /snippet -->

<!-- snippet: section_06.principles.planning.title -->
<!-- character: fixed -->
2. תכנון ורישוי
<!-- /snippet -->

<!-- snippet: section_06.principles.planning.zoning -->
<!-- character: semi -->
בהתאם לתכניות בניין עיר שבתוקף החלקה בה ממוקמת הדירה שבנדון מסווגת ביעוד '{zoning}'.
<!-- /snippet -->

<!-- snippet: section_06.principles.planning.permit -->
<!-- character: semi -->
הדירה שבנדון בנויה בהתאם להיתר בניה משנת {year}.
<!-- /snippet -->

<!-- snippet: section_06.principles.planning.no_permit -->
<!-- character: fixed -->
לא אותר היתר הבנייה המקורי של הבניין.
<!-- /snippet -->

<!-- snippet: section_06.principles.planning.completion -->
<!-- character: semi -->
תעודת גמר לבניין ניתנה בשנת {year}.
<!-- /snippet -->

<!-- snippet: section_06.principles.legal.title -->
<!-- character: fixed -->
3. מצב משפטי
<!-- /snippet -->

<!-- snippet: section_06.principles.legal.registered -->
<!-- character: fixed -->
החלקה בה ממוקמת הדירה שבנדון נרשמה בפנקס הבתים המשותפים, באופן בו כל תת חלקה מהווה יחידה עצמאית מבחינה משפטית.
<!-- /snippet -->

<!-- snippet: section_06.principles.legal.owner -->
<!-- character: semi -->
הדירה שבנדון רשומה על שם {owner}.
<!-- /snippet -->

<!-- snippet: section_06.principles.legal.rented -->
<!-- character: fixed -->
נכון למועד הביקור, הדירה מושכרת בשכירות חופשית.
<!-- /snippet -->

<!-- snippet: section_06.principles.legal.not_rented -->
<!-- character: fixed -->
נכון למועד הביקור, הדירה אינה מושכרת.
<!-- /snippet -->

<!-- snippet: section_06.principles.calc.title -->
<!-- character: fixed -->
4. עקרונות התחשיב
<!-- /snippet -->

<!-- snippet: section_06.principles.calc.free -->
<!-- character: fixed -->
אומדן השווי נערך לנכס שבנדון כחופשי מכל הערה, חוב ושעבוד.
<!-- /snippet -->

<!-- snippet: section_06.principles.calc.market -->
<!-- character: fixed -->
הובא בחשבון מצב שוק המקרקעין ומחירי נכסים דומים ורלוונטיים בסביבת הנכס וסביב המועד הקובע לחוות הדעת.
<!-- /snippet -->

<!-- snippet: section_06.comparison.heading -->
<!-- character: fixed -->
ב. נתוני השוואה
<!-- /snippet -->

<!-- snippet: section_06.comparison.header.no -->
<!-- character: fixed -->
מס'
<!-- /snippet -->

<!-- snippet: section_06.comparison.header.address -->
<!-- character: fixed -->
כתובת
<!-- /snippet -->

<!-- snippet: section_06.comparison.header.floor -->
<!-- character: fixed -->
קומה
<!-- /snippet -->

<!-- snippet: section_06.comparison.header.rooms -->
<!-- character: fixed -->
חד'
<!-- /snippet -->

<!-- snippet: section_06.comparison.header.built_area -->
<!-- character: fixed -->
שטח בנוי מ"ר
<!-- /snippet -->

<!-- snippet: section_06.comparison.header.balcony_area -->
<!-- character: fixed -->
מרפסת מ"ר
<!-- /snippet -->

<!-- snippet: section_06.comparison.header.equiv_area -->
<!-- character: fixed -->
שטח אקו' מ"ר
<!-- /snippet -->

<!-- snippet: section_06.comparison.header.price -->
<!-- character: fixed -->
מחיר
<!-- /snippet -->

<!-- snippet: section_06.comparison.header.price_per_sqm -->
<!-- character: fixed -->
₪/מ"ר אקו'
<!-- /snippet -->

<!-- snippet: section_06.comparison.header.notes -->
<!-- character: fixed -->
הערות
<!-- /snippet -->

<!-- snippet: section_06.comparison.summary -->
<!-- character: semi -->
לאור הנתונים שהוצגו לעיל, ובהתחשב במאפייני הנכס שבנדון ובמיקומו נראה כסביר לאמוד שווי מ"ר אקו' בנכס שבנדון בסך של כ- {price:,.0f} ₪ / מ"ר אקו'.
<!-- /snippet -->

<!-- snippet: section_06.comparison.missing -->
<!-- character: fixed -->
יש להשלים — נתוני עסקאות השוואה יש להוסיף ידנית.
<!-- /snippet -->

<!-- snippet: section_06.comparison.cell.empty -->
<!-- character: fixed -->
—
<!-- /snippet -->

<!-- snippet: section_06.comparison.cell.price_per_sqm -->
<!-- character: semi -->
{price:,.0f} ₪
<!-- /snippet -->

<!-- snippet: section_06.valuation.heading -->
<!-- character: fixed -->
ג. שומה
<!-- /snippet -->

<!-- snippet: section_06.valuation.intro -->
<!-- character: semi -->
בהתבסס על כל האמור לעיל ובמיקומו של הנכס המהווה את תת חלקה {sub_parcel} בחלקה מספר {parcel} בגוש {block}, ברחוב {address}:
<!-- /snippet -->

<!-- snippet: section_06.valuation.final -->
<!-- character: semi -->
אומדן שווי הזכויות בנכס שבנדון הינו סביב {value} ({words} שקלים חדשים) כולל מע"מ.
<!-- /snippet -->

<!-- snippet: section_06.valuation.rapid -->
<!-- character: semi -->
לצורך מימוש מהיר בדרך של מכירה באילוץ, ניתן להעמיד את שווי הנכס על סך של 85% מהשווי הנקוב לעיל, קרי: {value} ({words} שקלים חדשים).
<!-- /snippet -->

<!-- snippet: section_06.evacuation.alt_a -->
<!-- character: fixed -->
חלופה א' — שווי קיים
<!-- /snippet -->

<!-- snippet: section_06.evacuation.alt_b -->
<!-- character: fixed -->
חלופה ב' — שווי עתידי
<!-- /snippet -->

<!-- snippet: section_06.evacuation.entry -->
<!-- character: semi -->
{label}: {value} ({words} שקלים חדשים).
<!-- /snippet -->

<!-- snippet: section_06.declarations.heading -->
<!-- character: fixed -->
הצהרות
<!-- /snippet -->

<!-- snippet: section_06.declarations.no_interest -->
<!-- character: fixed -->
הננו מצהירים כי אין לנו עניין אישי עם הנכס שבנדון, בעלי הזכויות בנכס או עם מזמין חוות הדעת.
<!-- /snippet -->

<!-- snippet: section_06.declarations.ethics -->
<!-- character: fixed -->
חוות הדעת נערכה על פי תקנות שמאי המקרקעין (אתיקה מקצועית) התשכ"ו – 1966 ועל פי התקנים המקצועיים של הועדה לתקינה שמאית במועצת שמאי המקרקעין.
<!-- /snippet -->

<!-- snippet: section_06.declarations.scope -->
<!-- character: fixed -->
שומה זו הוכנה עבור מזמינה ולמטרתה בלבד. אין היא מהווה תחליף לייעוץ משפטי ואין להסתמך עליה לכל מטרה אחרת. השימוש בשומה נאסר על כל צד שלישי שהוא, אשר אינו המזמין ועורך השומה לא יהא אחראי להסתמכות כלשהי כאמור.
<!-- /snippet -->

