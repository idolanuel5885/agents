# SKILL: המצב המשפטי

## מה זה
פירוט הזכויות הרשומות בנכס. המבנה משתנה לפי סוג הזכויות.

## מקורות מידע
- נסח טאבו: tabu.justice.gov.il (נאסף אוטומטית)
- הסכם שכירות: מוגש על ידי הלקוח (ידני)
- הסכם רכישה / אישור זכויות: מוגש על ידי הלקוח (ידני)
- חוזה חכירה: מוגש על ידי הלקוח (ידני)

---

## תת-חלק א': נסח רישום מקרקעין (תמיד מופיע)

### בעלות פרטית — פנקס הבתים המשותפים
```
על פי העתק רישום מפנקס הבתים המשותפים, אשר הופק על ידי הח"מ
בתאריך [תאריך] באמצעות האינטרנט, עולים, בין היתר, הפרטים הבאים:

גוש          : [X]
חלקה         : [X]
תת חלקה      : [X]
תיאור הדירה  : דירה
תיאור קומה   : [שמינית / ראשונה וכו']
שטח במ"ר     : [X]
החלק ברכוש המשותף : [X/Y]

בעלויות:
[שם] – [חלק יחסי / בשלמות]

הערות:
[הערת אזהרה X — לטובת Y]
[הערה בדבר העברה לזרים וכו']
```

### חכירה מרמ"י — פנקס הזכויות
```
על פי העתק רישום מפנקס הזכויות, אשר הופק על ידי הח"מ
בתאריך [תאריך] באמצעות האינטרנט, עולים, בין היתר, הפרטים הבאים:

גוש     : [X]
חלקה    : [X]
בעלויות : קרן קיימת לישראל / רשות הפיתוח / מדינת ישראל — בשלמות
```

---

## תת-חלק ב': תשריט בית משותף (תמיד מופיע כשיש רישום)

```
להלן תכנית קומה [X] מתוך תשריט הבית המשותף:
[תמונה — עם סימון הדירה שבנדון]

להלן תכנית קומת [קרקע/מרתף] מתוך תשריט הבית המשותף:
[תמונה — עם סימון מקום החניה]
```

---

## תת-חלקים מותנים

### חוזה חכירה (כשהזכויות הן חכירה מרמ"י)
```
על פי חוזה חכירה מיום [תאריך] שנחתם בין רשות מקרקעי ישראל
לבין [שם החוכר] עולים בין היתר הפרטים הבאים:

מגרש/מגרשים  : [מספרים]
שטח           : כ- X מ"ר
תקופת החכירה  : 98 שנים, [תאריך התחלה] – [תאריך סיום]
אופציה        : 98 שנים החל מתום תקופת החכירה
מטרת החכירה  : מגורים — X יח"ד
```

### אישור זכויות מרמ"י (כשהדירה נרכשה מחברה על קרקע רמ"י)
```
על פי אישור זכויות אשר התקבל מרמ"י ביום [תאריך] עולים
בין היתר הפרטים הבאים:

גוש          : [X]
חלקות        : [X]
בעל זכויות   : [שם החברה]
הסכם חכירה   : מהוון עד תאריך [X]
משכנתא       : לטובת [בנק] מיום [X] בדרגה ראשונה
```

### הסכם רכישה (כשרלוונטי)
```
בהתאם להסכם רכישה מיום [תאריך] בין [מוכר] לבין [קונה]
עולים בין היתר הפרטים הבאים:

מגרש/מבנה/דירה : [פרטים]
הצמדות          : [מחסן, חניות]
תמורה           : X ₪
מועד מסירת החזקה: [תאריך]
```

### הסכם שכירות (כמעט תמיד מופיע)
```
בהתאם להסכם שכירות בלתי מוגנת אשר נחתם בתאריך [X],
בין [משכיר] לבין [שוכר] עולים הפרטים הבאים:

המושכר        : דירה בת X חדרים, בקומה ה-Y, ברחוב Z
תקופת השכירות : עד [תאריך] [+ אופציה אם יש]
דמי השכירות   : X ₪ לחודש
```

---

## כללי כתיבה
- לא לכלול פרטים שלא סופקו — לסמן "חסר" במקום
- הערות אזהרה: לפרט מה ולטובת מי
- שמות בעלי זכויות: כמו שרשום בטאבו (שם משפחה ראשון)
- חלקים יחסיים: 1/2, 3/4 — לא אחוזים

---

## Generator snippets

<!-- snippet: section_05.heading -->
<!-- character: fixed -->
המצב המשפטי
<!-- /snippet -->

<!-- snippet: section_05.registration.heading -->
<!-- character: fixed -->
א. נסח רישום מקרקעין
<!-- /snippet -->

<!-- snippet: section_05.registration.intro -->
<!-- character: semi -->
על פי העתק רישום מפנקס הבתים המשותפים, אשר הופק על ידי הח"מ בתאריך {registration_date} באמצעות האינטרנט, עולים, בין היתר, הפרטים הבאים:
<!-- /snippet -->

<!-- snippet: section_05.registration.label.block -->
<!-- character: fixed -->
גוש
<!-- /snippet -->

<!-- snippet: section_05.registration.label.parcel -->
<!-- character: fixed -->
חלקה
<!-- /snippet -->

<!-- snippet: section_05.registration.label.sub_parcel -->
<!-- character: fixed -->
תת חלקה
<!-- /snippet -->

<!-- snippet: section_05.registration.label.floor_description -->
<!-- character: fixed -->
תיאור קומה
<!-- /snippet -->

<!-- snippet: section_05.registration.label.area -->
<!-- character: fixed -->
שטח
<!-- /snippet -->

<!-- snippet: section_05.registration.label.common_share -->
<!-- character: fixed -->
החלק ברכוש המשותף
<!-- /snippet -->

<!-- snippet: section_05.registration.label.owners -->
<!-- character: fixed -->
בעלויות
<!-- /snippet -->

<!-- snippet: section_05.registration.label.notes -->
<!-- character: fixed -->
הערות
<!-- /snippet -->

<!-- snippet: section_05.registration.notes_default -->
<!-- character: fixed -->
לא נרשמו הערות
<!-- /snippet -->

<!-- snippet: section_05.registration.area_value -->
<!-- character: semi -->
{area:.0f} מ"ר
<!-- /snippet -->

<!-- snippet: section_05.diagram.heading -->
<!-- character: fixed -->
ב. תשריט בית משותף
<!-- /snippet -->

<!-- snippet: section_05.diagram.para -->
<!-- character: semi -->
להלן תכנית קומה {floor} מתוך תשריט הבית המשותף: [הכנס תמונה]
<!-- /snippet -->

<!-- snippet: section_05.rental.heading -->
<!-- character: fixed -->
ג. הסכם שכירות
<!-- /snippet -->

<!-- snippet: section_05.rental.intro -->
<!-- character: semi -->
בהתאם להסכם שכירות בלתי מוגנת אשר נחתם בתאריך {rental_agreement_date}, בין {landlord_name} לבין {tenant_name}, עולים הפרטים הבאים:
<!-- /snippet -->

<!-- snippet: section_05.rental.label.address -->
<!-- character: fixed -->
המושכר
<!-- /snippet -->

<!-- snippet: section_05.rental.label.period -->
<!-- character: fixed -->
תקופת השכירות
<!-- /snippet -->

<!-- snippet: section_05.rental.label.rent -->
<!-- character: fixed -->
דמי השכירות
<!-- /snippet -->

<!-- snippet: section_05.rental.period_value -->
<!-- character: semi -->
{start} — {end}
<!-- /snippet -->

<!-- snippet: section_05.rental.rent_value -->
<!-- character: semi -->
{rent} לחודש
<!-- /snippet -->

