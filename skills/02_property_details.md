# SKILL: טבלת פרטי הנכס

## מה זה
טבלה מובנית בתחילת הדוח המסכמת את כל הפרטים הבסיסיים. מופיעה בכל דוח ללא יוצא מן הכלל.

## מקור המידע
- רוב השדות: מהקלט (הזין המשתמש)
- שטח דירה בנוי: מתשריט היתר הבניה (נאסף אוטומטית או מוזן ידנית)
- נסח טאבו: מהרישום (נאסף אוטומטית)

## שורות קבועות (תמיד מופיעות)
```
מטרת חוות הדעת    : [מטרה]
מזמין חוות הדעת   : [שם]
בעלי הזכויות בנכס : [שם + חלק יחסי אם רלוונטי]
המועד הקובע        : [תאריך]
מועד הביקור בנכס  : [תאריך] [הערת שוליים: שם מי ביצע הביקור]

פרטי הנכס:
גוש               : [מספר]
חלקה              : [מספר]
תת חלקה           : [מספר]
הבניין בשלמות     : [בניין מגורים בן X קומות מעל קומת כניסה הכולל Y יח"ד]
הדירה שבנדון      : [דירת X חדרים הממוקמת בקומה ה-Z] — BOLD
שטח דירה רשום     : [X מ"ר]
שטח דירה בנוי     : [X מ"ר] [הערת שוליים: מקור המדידה]
מיקום             : [כתובת מלאה]
זכויות            : [בעלות פרטית / זכות חכירה מהוונת / זכות חוזית לחכירה]
```

## שורות מותנות
```
הצמדות            : [מופיע רק כשיש חניה / מחסן / גינה]
חלק מתת חלקה      : [מופיע רק בדירות שטרם נרשמו בפנקס הבתים המשותפים]
```

## כללי כתיבה
- הדירה שבנדון תמיד מודגשת (bold)
- שטח בנוי תמיד עם "כ-" (ערך מקורב)
- שטח רשום ללא "כ-" (ערך רשמי מהטאבו)
- זכויות:
  - דירה רגילה שנרשמה = "בעלות פרטית"
  - חכירה מרמ"י שהוסדרה = "זכות חכירה מהוונת"
  - רכישה מחברה שטרם נרשמה = "זכות חוזית לחכירה"

## הערות שוליים קבועות
- הביקור בנכס: "הביקור בנכס נערך על ידי [שם], [תפקיד], [בנוכחות X]"
- שטח בנוי: "שטח הדירה הבנוי הינו בהתאם ל[מקור — היתר/תשריט/מדידה גרפית]"

---

## Generator snippets

<!-- snippet: rights.private -->
<!-- character: fixed -->
בעלות פרטית
<!-- /snippet -->

<!-- snippet: rights.lease_rami -->
<!-- character: fixed -->
זכות חכירה מהוונת מרשות מקרקעי ישראל
<!-- /snippet -->

<!-- snippet: rights.lease_company -->
<!-- character: fixed -->
זכות חוזית לחכירה מחברה משכנת
<!-- /snippet -->

<!-- snippet: section_02.heading -->
<!-- character: fixed -->
פרטי הנכס
<!-- /snippet -->

<!-- snippet: section_02.apt_desc -->
<!-- character: semi -->
דירת {rooms} חדרים הממוקמת בקומה ה-{floor_ord}
<!-- /snippet -->

<!-- snippet: section_02.building_desc -->
<!-- character: semi -->
בניין מגורים בן {total_floors} קומות מעל קומת כניסה הכולל {units_count} יח"ד
<!-- /snippet -->

<!-- snippet: section_02.attachment.parking_default -->
<!-- character: fixed -->
חניה
<!-- /snippet -->

<!-- snippet: section_02.attachment.storage_default -->
<!-- character: fixed -->
מחסן
<!-- /snippet -->

<!-- snippet: section_02.attachment.garden -->
<!-- character: semi -->
גינה ({garden_area:.0f} מ"ר)
<!-- /snippet -->

<!-- snippet: section_02.label.purpose -->
<!-- character: fixed -->
מטרת חוות הדעת
<!-- /snippet -->

<!-- snippet: section_02.label.client -->
<!-- character: fixed -->
מזמין חוות הדעת
<!-- /snippet -->

<!-- snippet: section_02.label.rights_owner -->
<!-- character: fixed -->
בעלי הזכויות בנכס
<!-- /snippet -->

<!-- snippet: section_02.label.determining_date -->
<!-- character: fixed -->
המועד הקובע
<!-- /snippet -->

<!-- snippet: section_02.label.visit_date -->
<!-- character: fixed -->
מועד הביקור בנכס
<!-- /snippet -->

<!-- snippet: section_02.label.block -->
<!-- character: fixed -->
גוש
<!-- /snippet -->

<!-- snippet: section_02.label.parcel -->
<!-- character: fixed -->
חלקה
<!-- /snippet -->

<!-- snippet: section_02.label.sub_parcel -->
<!-- character: fixed -->
תת חלקה
<!-- /snippet -->

<!-- snippet: section_02.label.building -->
<!-- character: fixed -->
הבניין בשלמות
<!-- /snippet -->

<!-- snippet: section_02.label.apartment -->
<!-- character: fixed -->
הדירה שבנדון
<!-- /snippet -->

<!-- snippet: section_02.label.registered_area -->
<!-- character: fixed -->
שטח דירה רשום
<!-- /snippet -->

<!-- snippet: section_02.label.built_area -->
<!-- character: fixed -->
שטח דירה בנוי
<!-- /snippet -->

<!-- snippet: section_02.label.location -->
<!-- character: fixed -->
מיקום
<!-- /snippet -->

<!-- snippet: section_02.label.rights -->
<!-- character: fixed -->
זכויות
<!-- /snippet -->

<!-- snippet: section_02.label.attachments -->
<!-- character: fixed -->
הצמדות
<!-- /snippet -->

<!-- snippet: section_02.value.registered_area -->
<!-- character: semi -->
{area:.0f} מ"ר
<!-- /snippet -->

<!-- snippet: section_02.value.built_area -->
<!-- character: semi -->
כ- {area:.0f} מ"ר
<!-- /snippet -->

