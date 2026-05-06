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
בעלות פרטית
<!-- /snippet -->

<!-- snippet: rights.lease_rami -->
זכות חכירה מהוונת מרשות מקרקעי ישראל
<!-- /snippet -->

<!-- snippet: rights.lease_company -->
זכות חוזית לחכירה מחברה משכנת
<!-- /snippet -->

<!-- snippet: section_02.heading -->
פרטי הנכס
<!-- /snippet -->

<!-- snippet: section_02.apt_desc -->
דירת {rooms} חדרים הממוקמת בקומה ה-{floor_ord}
<!-- /snippet -->

<!-- snippet: section_02.building_desc -->
בניין מגורים בן {total_floors} קומות מעל קומת כניסה הכולל {units_count} יח"ד
<!-- /snippet -->

<!-- snippet: section_02.attachment.parking_default -->
חניה
<!-- /snippet -->

<!-- snippet: section_02.attachment.storage_default -->
מחסן
<!-- /snippet -->

<!-- snippet: section_02.attachment.garden -->
גינה ({garden_area:.0f} מ"ר)
<!-- /snippet -->

<!-- snippet: section_02.label.purpose -->
מטרת חוות הדעת
<!-- /snippet -->

<!-- snippet: section_02.label.client -->
מזמין חוות הדעת
<!-- /snippet -->

<!-- snippet: section_02.label.rights_owner -->
בעלי הזכויות בנכס
<!-- /snippet -->

<!-- snippet: section_02.label.determining_date -->
המועד הקובע
<!-- /snippet -->

<!-- snippet: section_02.label.visit_date -->
מועד הביקור בנכס
<!-- /snippet -->

<!-- snippet: section_02.label.block -->
גוש
<!-- /snippet -->

<!-- snippet: section_02.label.parcel -->
חלקה
<!-- /snippet -->

<!-- snippet: section_02.label.sub_parcel -->
תת חלקה
<!-- /snippet -->

<!-- snippet: section_02.label.building -->
הבניין בשלמות
<!-- /snippet -->

<!-- snippet: section_02.label.apartment -->
הדירה שבנדון
<!-- /snippet -->

<!-- snippet: section_02.label.registered_area -->
שטח דירה רשום
<!-- /snippet -->

<!-- snippet: section_02.label.built_area -->
שטח דירה בנוי
<!-- /snippet -->

<!-- snippet: section_02.label.location -->
מיקום
<!-- /snippet -->

<!-- snippet: section_02.label.rights -->
זכויות
<!-- /snippet -->

<!-- snippet: section_02.label.attachments -->
הצמדות
<!-- /snippet -->

<!-- snippet: section_02.value.registered_area -->
{area:.0f} מ"ר
<!-- /snippet -->

<!-- snippet: section_02.value.built_area -->
כ- {area:.0f} מ"ר
<!-- /snippet -->

