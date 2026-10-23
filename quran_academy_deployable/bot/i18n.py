"""Multilingual internationalization (i18n) engine for Online Quran Academy Bot.
Supports English (en), Amharic (am), Afaan Oromoo (om), and Arabic (ar).
"""
import db

SUPPORTED_LANGUAGES = {
    "en": {"label": "🇬🇧 English", "name": "English"},
    "am": {"label": "🇪🇹 አማርኛ", "name": "Amharic"},
    "om": {"label": "🌳 Afaan Oromoo", "name": "Oromic"},
    "ar": {"label": "🇸🇦 العربية", "name": "Arabic"},
}

DEFAULT_LANGUAGE = "en"

STRINGS = {
    # -----------------------------------------------------------------------
    # Language Selection Banner
    # -----------------------------------------------------------------------
    "choose_lang_title": {
        "en": (
            "🌐 <b>Welcome to Online Quran Academy!</b>\n\n"
            "Please select your preferred language to get started:\n\n"
            "🇪🇹 እባክዎ ቋንቋዎን ይምረጡ፡\n"
            "🌳 Maaloo afaan keessan filadhaa:\n"
            "🇸🇦 الرجاء اختيار لغتكم المفضلة:"
        ),
        "am": (
            "🌐 <b>ቋንቋ ይምረጡ / Select Language</b>\n\n"
            "እባክዎ ለመቀጠል የሚፈልጉትን ቋንቋ ይምረጡ፡"
        ),
        "om": (
            "🌐 <b>Afaan Filadhaa / Select Language</b>\n\n"
            "Maaloo itti fufuuf afaan keessan filadhaa:"
        ),
        "ar": (
            "🌐 <b>اختيار اللغة / Select Language</b>\n\n"
            "الرجاء اختيار لغتكم المفضلة للمتابعة:"
        ),
    },
    "lang_changed": {
        "en": "✅ Language changed to English!",
        "am": "✅ ቋንቋዎ ወደ አማርኛ ተቀይሯል!",
        "om": "✅ Afaan gara Afaan Oromootti jijjiirameera!",
        "ar": "✅ تم تغيير اللغة إلى العربية بنجاح!",
    },

    # -----------------------------------------------------------------------
    # Welcome & Greeting
    # -----------------------------------------------------------------------
    "welcome_greeting": {
        "en": "Assalamu Alaikum wa Rahmatullahi wa Barakatuh!",
        "am": "አሰላሙ አለይኩም ወራሕመቱላሂ ወበረካቱህ!",
        "om": "Assalaamu Aleykum Warahmatullaahi Wabarakaatuhu!",
        "ar": "السلام عليكم ورحمة الله وبركاته!",
    },
    "welcome_body": {
        "en": (
            "Assalamu Alaikum wa Rahmatullahi wa Barakatuh!\n\n"
            "Welcome to <b>{academy_name}</b>.\n"
            "<i>{tagline}</i>\n\n"
            "Learn the Quran and Islamic knowledge through structured online programs "
            "designed for different learning levels.\n\n"
            "Choose an option below to get started:"
        ),
        "am": (
            "አሰላሙ አለይኩም ወራሕመቱላሂ ወበረካቱህ!\n\n"
            "ወደ <b>{academy_name}</b> በደህና መጡ።\n"
            "<i>{tagline}</i>\n\n"
            "የተከበረውን ቁርኣን እና እስላማዊ ዕውቀትን በተለያዩ የትምህርት ደረጃዎች በተዘጋጁ የመስመር ላይ ፕሮግራሞች ይማሩ።\n\n"
            "ለመጀመር ከታች ካሉት አማራጮች አንዱን ይምረጡ፡"
        ),
        "om": (
            "Assalaamu Aleykum Warahmatullaahi Wabarakaatuhu!\n\n"
            "Baga gara <b>{academy_name}</b> nagaan dhuftan.\n"
            "<i>{tagline}</i>\n\n"
            "Qur'aana kabajamaa fi beekumsa Islaamaa sagantaalee toora intarneetii sadarkaa adda addaatiif qophaa'aniin baradhaa.\n\n"
            "Jalqabuuf filannoowwan armaan gadii keessaa filadhaa:"
        ),
        "ar": (
            "السلام عليكم ورحمة الله وبركاته!\n\n"
            "أهلاً وسهلاً بكم في <b>{academy_name}</b>.\n"
            "<i>{tagline}</i>\n\n"
            "تعلّم القرآن الكريم والعلوم الشرعية عبر الإنترنت من خلال برامج تعليمية متميزة تناسب جميع المستويات.\n\n"
            "اختر أحد الخيارات أدناه للبدء:"
        ),
    },
    "resume_note": {
        "en": "\n\n<i>Note: You have an unfinished registration. Tap 'Register as a Student' to resume.</i>",
        "am": "\n\n<i>ማሳሰቢያ፡ ያላለቀ የምዝገባ ሂደት አለዎት። ለመቀጠል 'በተማሪነት ይመዝገቡ' የሚለውን ይጫኑ።</i>",
        "om": "\n\n<i>Hubachiisa: Galmee hin xumuramne qabdu. Itti fufuuf 'Barataa Ta'aa Galmaa'aa' kan jedhu tuqaa.</i>",
        "ar": "\n\n<i>ملاحظة: لديك تسجيل غير مكتمل. اضغط على 'التسجيل كطالب' للمتابعة من حيث توقفت.</i>",
    },

    # -----------------------------------------------------------------------
    # Main Menu Buttons
    # -----------------------------------------------------------------------
    "btn_courses": {
        "en": "📚 Explore Courses",
        "am": "📚 ኮርሶችን ይመልከቱ",
        "om": "📚 Koorsiiwwan Ilaalaa",
        "ar": "📚 استعراض الدورات",
    },
    "btn_register": {
        "en": "📝 Register as a Student",
        "am": "📝 በተማሪነት ይመዝገቡ",
        "om": "📝 Barataa Ta'aa Galmaa'aa",
        "ar": "📝 التسجيل كطالب",
    },
    "btn_fees": {
        "en": "💰 Monthly Fees",
        "am": "💰 ወርሃዊ ክፍያዎች",
        "om": "💰 Kaffaltii Ji'aa",
        "ar": "💰 الرسوم الشهرية",
    },
    "btn_profile": {
        "en": "👤 My Profile",
        "am": "👤 የእኔ መገለጫ",
        "om": "👤 Piroofayilii Koo",
        "ar": "👤 ملفي الشخصي",
    },
    "btn_schedule": {
        "en": "📅 Class Schedule",
        "am": "📅 የክፍል ፕሮግራም",
        "om": "📅 Sagantaa Daree",
        "ar": "📅 جدول الحصص",
    },
    "btn_progress": {
        "en": "📊 My Learning Progress",
        "am": "📊 የትምህርት እድገቴ",
        "om": "📊 Sadarkaa Barnoota Koo",
        "ar": "📊 تقدمي في التعلم",
    },
    "btn_help": {
        "en": "❓ Help and Contact",
        "am": "❓ እርዳታ እና አግኙን",
        "om": "❓ Gargaarsa fi Qunnamtii",
        "ar": "❓ المساعدة والتواصل",
    },
    "btn_language": {
        "en": "🌐 Language (ቋንቋ / Afaan / اللغة)",
        "am": "🌐 ቋንቋ ይቀይሩ (Language)",
        "om": "🌐 Afaan Jijjiiraa (Language)",
        "ar": "🌐 تغيير اللغة (Language)",
    },
    "btn_admin": {
        "en": "🛡️ Open Admin Bot (@xmzgebaadminbot)",
        "am": "🛡️ አድሚን ቦት (@xmzgebaadminbot)",
        "om": "🛡️ Admin Boti Bani (@xmzgebaadminbot)",
        "ar": "🛡️ فتح بوت الإدارة (@xmzgebaadminbot)",
    },
    "btn_sheet": {
        "en": "📊 Demo: Live Google Sheet",
        "am": "📊 የቀጥታ Google Sheet ይመልከቱ",
        "om": "📊 Google Sheet Kallattii Ilaalaa",
        "ar": "📊 عرض جدول جوجل المباشر",
    },

    # -----------------------------------------------------------------------
    # Common Navigation
    # -----------------------------------------------------------------------
    "btn_back": {
        "en": "🔙 Back",
        "am": "🔙 ተመለስ",
        "om": "🔙 Duubatti",
        "ar": "🔙 رجوع",
    },
    "btn_back_courses": {
        "en": "🔙 Back to Courses",
        "am": "🔙 ወደ ኮርሶች ተመለስ",
        "om": "🔙 Gara Koorsiiwwaniitti",
        "ar": "🔙 العودة إلى الدورات",
    },
    "btn_back_kitabs": {
        "en": "🔙 Back to Kitabs",
        "am": "🔙 ወደ ኪታቦች ተመለስ",
        "om": "🔙 Gara Kitaabotaatti",
        "ar": "🔙 العودة إلى الكتب",
    },
    "btn_main_menu": {
        "en": "🏠 Main Menu",
        "am": "🏠 ዋና ማውጫ",
        "om": "🏠 Baafata Guddaa",
        "ar": "🏠 القائمة الرئيسية",
    },
    "btn_cancel": {
        "en": "❌ Cancel Registration",
        "am": "❌ ምዝገባ ሰርዝ",
        "om": "❌ Galmee Haqi",
        "ar": "❌ إلغاء التسجيل",
    },
    "btn_reg_course": {
        "en": "📝 Register for this Course",
        "am": "📝 ለዚህ ኮርስ ይመዝገቡ",
        "om": "📝 Koorsii Kanaaf Galmaa'aa",
        "ar": "📝 التسجيل في هذه الدورة",
    },

    # -----------------------------------------------------------------------
    # Course Titles & Categories
    # -----------------------------------------------------------------------
    "cat_qaida": {
        "en": "Qaida",
        "am": "ቃዒዳ",
        "om": "Qaa'idaa",
        "ar": "القاعدة",
    },
    "cat_nezer": {
        "en": "Nezer",
        "am": "ነዘር",
        "om": "Nazar",
        "ar": "النظر",
    },
    "cat_tajweed": {
        "en": "Tajweed",
        "am": "ተጅዊድ",
        "om": "Tajwiida",
        "ar": "التجويد",
    },
    "cat_hifz": {
        "en": "Hifz",
        "am": "ሒፍዝ",
        "om": "Hifzii",
        "ar": "الحفظ",
    },
    "cat_kitab": {
        "en": "Kitab",
        "am": "ኪታብ",
        "om": "Kitaaba",
        "ar": "الكتب الشرعية",
    },
    "cat_arabic": {
        "en": "Arabic Language",
        "am": "አረብኛ ቋንቋ",
        "om": "Afaan Arabaa",
        "ar": "اللغة العربية",
    },
    "cat_islamic_studies": {
        "en": "Islamic Studies",
        "am": "እስላማዊ ትምህርቶች",
        "om": "Barnoota Islaamaa",
        "ar": "الدراسات الإسلامية",
    },

    # -----------------------------------------------------------------------
    # Course Catalog View
    # -----------------------------------------------------------------------
    "courses_title": {
        "en": (
            "📚 <b>{academy_name} — Available Courses</b>\n\n"
            "Learn the Holy Quran and Islamic sciences through structured programs designed for all learning levels.\n\n"
            "Select a course below to view syllabus and enrollment details:"
        ),
        "am": (
            "📚 <b>{academy_name} — የሚሰጡ ኮርሶች</b>\n\n"
            "የተከበረውን ቁርኣን እና እስላማዊ ዕውቀትን በደረጃ በተዘጋጁ ፕሮግራሞች ይማሩ።\n\n"
            "ዝርዝሩን እና የትምህርት መርሃ-ግብሩን ለማየት ከታች ኮርስ ይምረጡ፡"
        ),
        "om": (
            "📚 <b>{academy_name} — Koorsiiwwan Jiranii</b>\n\n"
            "Qur'aana kabajamaa fi barnoota Islaamaa sagantaalee sirnaawaan baradhaa.\n\n"
            "Odeeffannoo fi qajeelfama galmee arguuf koorsii filadhaa:"
        ),
        "ar": (
            "📚 <b>{academy_name} — الدورات المتاحة</b>\n\n"
            "تعلّم القرآن الكريم والعلوم الشرعية عبر برامج متخصصة تناسب جميع المستويات.\n\n"
            "اختر الدورة أدناه لعرض تفاصيل المنهج والتسجيل:"
        ),
    },
    "kitabs_catalog_title": {
        "en": (
            "📚 <b>Available Kitabs (Islamic Books)</b>\n\n"
            "Below is the comprehensive list of classical texts and Kitabs currently taught at the academy.\n\n"
            "Select any Kitab below to view its syllabus, author, and enrollment details:"
        ),
        "am": (
            "📚 <b>የሚሰጡ የኪታብ ትምህርቶች</b>\n\n"
            "በአካዳሚው የሚሰጡ ታዋቂ የእስልምና ኪታቦች እና ጽሑፎች ዝርዝር ከታች ይገኛል።\n\n"
            "ዝርዝሩን ለማየት የሚፈልጉትን ኪታብ ይምረጡ፡"
        ),
        "om": (
            "📚 <b>Kitaabota Islaamaa Jiranii</b>\n\n"
            "Tarreen kitaabota beekamoo akaadaamii keessatti barsiifamanii armaan gadi jira.\n\n"
            "Odeeffannoo baruuf kitaaba barbaaddan filadhaa:"
        ),
        "ar": (
            "📚 <b>الكتب والمتون الشرعية المتاحة</b>\n\n"
            "فيما يلي قائمة بالمتون والكتب المعتمدة التي تُدرّس في الأكاديمية.\n\n"
            "اختر أي كتاب لعرض تفاصيله ومؤلفه والتسجيل به:"
        ),
    },
    "course_detail_card": {
        "en": (
            "📖 <b>{name}</b>\n\n"
            "<b>Description:</b>\n{desc}\n\n"
            "🎯 <b>Level:</b> {level}\n"
            "👥 <b>Age Group:</b> {age}\n"
            "💻 <b>Class Format:</b> {fmt}\n"
            "⏱ <b>Duration:</b> {duration}\n"
            "📅 <b>Frequency:</b> {frequency}\n"
            "💰 <b>Monthly Fee:</b> {fee}\n"
        ),
        "am": (
            "📖 <b>{name}</b>\n\n"
            "<b>ማብራሪያ፡</b>\n{desc}\n\n"
            "🎯 <b>ደረጃ፡</b> {level}\n"
            "👥 <b>የእድሜ ክልል፡</b> {age}\n"
            "💻 <b>የትምህርት አሰጣጥ፡</b> {fmt}\n"
            "⏱ <b>የክፍለ ጊዜ ርዝመት፡</b> {duration}\n"
            "📅 <b>በሳምንት፡</b> {frequency}\n"
            "💰 <b>ወርሃዊ ክፍያ፡</b> {fee}\n"
        ),
        "om": (
            "📖 <b>{name}</b>\n\n"
            "<b>Ibsa:</b>\n{desc}\n\n"
            "🎯 <b>Sadarkaa:</b> {level}\n"
            "👥 <b>Umrii:</b> {age}\n"
            "💻 <b>Haala Barnootaa:</b> {fmt}\n"
            "⏱ <b>Yeroo:</b> {duration}\n"
            "📅 <b>Torbanitti:</b> {frequency}\n"
            "💰 <b>Kaffaltii Ji'aa:</b> {fee}\n"
        ),
        "ar": (
            "📖 <b>{name}</b>\n\n"
            "<b>الوصف:</b>\n{desc}\n\n"
            "🎯 <b>المستوى:</b> {level}\n"
            "👥 <b>الفئة العمرية:</b> {age}\n"
            "💻 <b>طريقة الدراسة:</b> {fmt}\n"
            "⏱ <b>مدة الحصة:</b> {duration}\n"
            "📅 <b>عدد الحصص:</b> {frequency}\n"
            "💰 <b>الرسوم الشهرية:</b> {fee}\n"
        ),
    },

    # -----------------------------------------------------------------------
    # Registration Flow
    # -----------------------------------------------------------------------
    "reg_step1_cat": {
        "en": (
            "📝 <b>Student Registration — Step 1: Course Category</b>\n\n"
            "Please select the learning program you wish to join:\n"
            "<i>(Tap a course category below to begin)</i>"
        ),
        "am": (
            "📝 <b>የተማሪ ምዝገባ — ደረጃ 1፡ የኮርስ ምርጫ</b>\n\n"
            "እባክዎ መማር የሚፈልጉትን የትምህርት ዘርፍ ይምረጡ፡\n"
            "<i>(ለመጀመር ከታች ይጫኑ)</i>"
        ),
        "om": (
            "📝 <b>Galmee Barataa — Sadarkaa 1: Koorsii Filachuu</b>\n\n"
            "Maaloo sagantaa barachuu barbaaddan filadhaa:\n"
            "<i>(Jalqabuuf armaan gaditti tuqaa)</i>"
        ),
        "ar": (
            "📝 <b>تسجيل طالب جديد — الخطوة 1: اختيار الدورة</b>\n\n"
            "الرجاء اختيار البرنامج التعليمي الذي ترغب بالانضمام إليه:\n"
            "<i>(اضغط على أحد الخيارات أدناه للبدء)</i>"
        ),
    },
    "reg_step1_kitab": {
        "en": (
            "📚 <b>Select a Kitab (Islamic Book)</b>\n\n"
            "Please select the specific Kitab you wish to register for from the available texts:"
        ),
        "am": (
            "📚 <b>ኪታብ ይምረጡ</b>\n\n"
            "እባክዎ መማር የሚፈልጉትን ኪታብ ከተዘረዘሩት ውስጥ ይምረጡ፡"
        ),
        "om": (
            "📚 <b>Kitaaba Filadhaa</b>\n\n"
            "Maaloo kitaaba barachuu barbaaddan tarree keessaa filadhaa:"
        ),
        "ar": (
            "📚 <b>اختيار الكتاب أو المتن الشرعي</b>\n\n"
            "الرجاء اختيار الكتاب المحدد الذي ترغب بدراسته من القائمة:"
        ),
    },
    "reg_step2_name": {
        "en": (
            "📝 <b>Student Registration — Step 2: Student Identity</b>\n\n"
            "Selected Course: <b>{course_name}</b>\n"
            "Monthly Fee: <b>{fee}</b>\n\n"
            "Please enter the <b>Full Name</b> of the student:\n"
            "<i>(Type and send the name as a message)</i>"
        ),
        "am": (
            "📝 <b>የተማሪ ምዝገባ — ደረጃ 2፡ የተማሪው ማንነት</b>\n\n"
            "የተመረጠው ኮርስ፡ <b>{course_name}</b>\n"
            "ወርሃዊ ክፍያ፡ <b>{fee}</b>\n\n"
            "እባክዎ የተማሪውን <b>ሙሉ ስም</b> ጽፈው ይላኩ፡\n"
            "<i>(መልእክት ጽፈው ይላኩ)</i>"
        ),
        "om": (
            "📝 <b>Galmee Barataa — Sadarkaa 2: Eenyummaa Barataa</b>\n\n"
            "Koorsii Filatame: <b>{course_name}</b>\n"
            "Kaffaltii Ji'aa: <b>{fee}</b>\n\n"
            "Maaloo <b>Maqaa Guutuu</b> barataa ergaa:\n"
            "<i>(Ergaa barreessaa ergaa)</i>"
        ),
        "ar": (
            "📝 <b>تسجيل طالب جديد — الخطوة 2: بيانات الطالب</b>\n\n"
            "الدورة المختارة: <b>{course_name}</b>\n"
            "الرسوم الشهرية: <b>{fee}</b>\n\n"
            "الرجاء كتابة <b>الاسم الثلاثي</b> للطالب وإرساله كرسالة:"
        ),
    },
    "reg_step3_age": {
        "en": "👤 Student: <b>{name}</b>\n\n🎂 Please enter the student's <b>Age</b> (e.g. 14, 25):",
        "am": "👤 ተማሪ፡ <b>{name}</b>\n\n🎂 እባክዎ የተማሪውን <b>እድሜ</b> ያስገቡ (ለምሳሌ፡ 14 ወይም 25)፡",
        "om": "👤 Barataa: <b>{name}</b>\n\n🎂 Maaloo <b>Umrii</b> barataa galchaa (fkn. 14 ykn 25):",
        "ar": "👤 الطالب: <b>{name}</b>\n\n🎂 الرجاء إدخال <b>عمر الطالب</b> (مثال: 14 أو 25):",
    },
    "reg_step_guardian_name": {
        "en": (
            "⚠️ <b>Parent / Guardian Information Required</b>\n\n"
            "Since the student is under 18 ({age} years old), please enter the "
            "<b>Parent or Guardian's Full Name</b>:"
        ),
        "am": (
            "⚠️ <b>የወላጅ / የአሳዳጊ መረጃ ያስፈልጋል</b>\n\n"
            "ተማሪው ከ18 ዓመት በታች ({age} ዓመት) ስለሆነ፣ እባክዎ የ<b>ወላጅ ወይም የአሳዳጊ ሙሉ ስም</b> ያስገቡ፡"
        ),
        "om": (
            "⚠️ <b>Odeeffannoo Maatii / Guddiftuu</b>\n\n"
            "Barataan umrii 18 gadi ({age} waggaa) waan ta'eef, maaloo <b>Maqaa Guutuu Maatii ykn Guddiftuu</b> galchaa:"
        ),
        "ar": (
            "⚠️ <b>بيانات ولي الأمر مطلوبة</b>\n\n"
            "نظراً لأن الطالب دون سن 18 عاماً (العمر: {age})، يُرجى إدخال <b>اسم ولي الأمر بالكامل</b>:"
        ),
    },
    "reg_step_guardian_phone": {
        "en": "📞 Please enter the <b>Parent or Guardian's Contact Phone Number</b>:",
        "am": "📞 እባክዎ የ<b>ወላጅ ወይም የአሳዳጊ ስልክ ቁጥር</b> ያስገቡ፡",
        "om": "📞 Maaloo <b>Lakkoofsa Bilbilaa Maatii ykn Guddiftuu</b> galchaa:",
        "ar": "📞 الرجاء إدخال <b>رقم هاتف ولي الأمر</b>:",
    },
    "reg_step_guardian_rel": {
        "en": "🤝 Relationship to student:",
        "am": "🤝 ከተማሪው ጋር ያለው ዝምድና፡",
        "om": "🤝 Walitti dhufeenya barataa wajjin:",
        "ar": "🤝 صلة القرابة بالطالب:",
    },
    "reg_rel_father": {
        "en": "Father",
        "am": "አባት",
        "om": "Abbaa",
        "ar": "الأب",
    },
    "reg_rel_mother": {
        "en": "Mother",
        "am": "እናት",
        "om": "Haadha",
        "ar": "الأم",
    },
    "reg_rel_guardian": {
        "en": "Guardian",
        "am": "አሳዳጊ",
        "om": "Guddiftuu",
        "ar": "ولي أمر / وصي",
    },
    "reg_step_location": {
        "en": (
            "📍 Please enter the student's <b>Country and City</b>\n"
            "<i>(e.g. Ethiopia, Addis Ababa or USA, Dallas)</i>:"
        ),
        "am": (
            "📍 እባክዎ የተማሪውን <b>ሀገር እና ከተማ</b> ያስገቡ\n"
            "<i>(ለምሳሌ፡ ኢትዮጵያ፣ አዲስ አበባ)</i>፡"
        ),
        "om": (
            "📍 Maaloo <b>Biyya fi Magaalaa</b> barataa galchaa\n"
            "<i>(fkn. Itoophiyaa, Finfinnee)</i>:"
        ),
        "ar": (
            "📍 الرجاء إدخال <b>الدولة والمدينة</b>\n"
            "<i>(مثال: إثيوبيا، أديس أبابا أو السعودية، الرياض)</i>:"
        ),
    },
    "reg_step_phone": {
        "en": (
            "📞 Please enter your <b>Phone Number with country code</b>\n"
            "<i>(Example: +251911223344 or +1234567890)</i>:"
        ),
        "am": (
            "📞 እባክዎ የ<b>ስልክ ቁጥርዎን ከአገር መለያ ኮድ ጋር</b> ያስገቡ\n"
            "<i>(ለምሳሌ፡ +251911223344)</i>፡"
        ),
        "om": (
            "📞 Maaloo <b>Lakkoofsa Bilbilaa koodii biyyaa wajjin</b> galchaa\n"
            "<i>(fkn. +251911223344)</i>:"
        ),
        "ar": (
            "📞 الرجاء إدخال <b>رقم الهاتف مع رمز الدولة</b>\n"
            "<i>(مثال: +251911223344 أو +966501234567)</i>:"
        ),
    },
    "reg_step_schedule": {
        "en": (
            "📅 <b>Preferred Class Schedule</b>\n\n"
            "Please select your preferred class time:"
        ),
        "am": (
            "📅 <b>ተመራጭ የትምህርት ሰዓት</b>\n\n"
            "እባክዎ ለእርስዎ ምቹ የሆነውን የክፍል ሰዓት ይምረጡ፡"
        ),
        "om": (
            "📅 <b>Yeroo Daree Filatamaa</b>\n\n"
            "Maaloo sa'aatii daree isiniif mijatu filadhaa:"
        ),
        "ar": (
            "📅 <b>الوقت المفضل للحصص</b>\n\n"
            "الرجاء اختيار الوقت الأنسب لك للدراسة:"
        ),
    },
    "sched_morning": {
        "en": "🌅 Morning",
        "am": "🌅 ጠዋት",
        "om": "🌅 Ganama",
        "ar": "🌅 صباحاً",
    },
    "sched_afternoon": {
        "en": "☀️ Afternoon",
        "am": "☀️ ከሰዓት",
        "om": "☀️ Guyyaa",
        "ar": "☀️ ظهراً / عصراً",
    },
    "sched_evening": {
        "en": "🌙 Evening",
        "am": "🌙 ምሽት",
        "om": "🌙 Galgala",
        "ar": "🌙 مساءً",
    },
    "sched_flexible": {
        "en": "🔄 Flexible",
        "am": "🔄 በማንኛውም ጊዜ",
        "om": "🔄 Yeroo Kamiyyuu",
        "ar": "🔄 وقت مرن",
    },
    "reg_step_payment": {
        "en": (
            "💳 <b>Registration Summary & Payment Instructions</b>\n\n"
            "👤 <b>Student:</b> {full_name}\n"
            "📚 <b>Program:</b> {program_name}\n"
            "📍 <b>Location:</b> {location}\n"
            "📞 <b>Phone:</b> {phone}\n"
            "📅 <b>Schedule:</b> {schedule}\n"
            "💰 <b>Monthly Tuition:</b> <b>{fee}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🏛️ <b>Official Payment Accounts:</b>\n"
            "• <b>Commercial Bank of Ethiopia (CBE):</b>\n"
            "  Account: <code>1000234567890</code>\n"
            "  Name: <i>Online Quran Academy</i>\n\n"
            "• <b>Telebirr:</b>\n"
            "  Number: <code>0911223344</code>\n"
            "  Name: <i>Online Quran Academy</i>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📸 <b>Final Step:</b>\n"
            "Please make the payment and <b>upload a photo or screenshot of your receipt</b> below to complete your registration:"
        ),
        "am": (
            "💳 <b>የምዝገባ ማጠቃለያ እና የክፍያ መመሪያ</b>\n\n"
            "👤 <b>ተማሪ፡</b> {full_name}\n"
            "📚 <b>ኮርስ፡</b> {program_name}\n"
            "📍 <b>አድራሻ፡</b> {location}\n"
            "📞 <b>ስልክ፡</b> {phone}\n"
            "📅 <b>ሰዓት፡</b> {schedule}\n"
            "💰 <b>ወርሃዊ ክፍያ፡</b> <b>{fee}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🏛️ <b>የአካዳሚው የክፍያ ሒሳቦች፡</b>\n"
            "• <b>የኢትዮጵያ ንግድ ባንክ (CBE)፡</b>\n"
            "  ሒሳብ ቁጥር፡ <code>1000234567890</code>\n"
            "  ስም፡ <i>Online Quran Academy</i>\n\n"
            "• <b>ቴሌብር (Telebirr)፡</b>\n"
            "  ስልክ፡ <code>0911223344</code>\n"
            "  ስም፡ <i>Online Quran Academy</i>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📸 <b>የመጨረሻው ደረጃ፡</b>\n"
            "እባክዎ ክፍያውን ፈጽመው የከፈሉበትን <b>የደረሰኝ ፎቶ ወይም ስክሪንሾት</b> ከታች ይላኩ፡"
        ),
        "om": (
            "💳 <b>Cuunfaa Galmee fi Qajeelfama Kaffaltii</b>\n\n"
            "👤 <b>Barataa:</b> {full_name}\n"
            "📚 <b>Koorsii:</b> {program_name}\n"
            "📍 <b>Bakka:</b> {location}\n"
            "📞 <b>Bilbila:</b> {phone}\n"
            "📅 <b>Yeroo:</b> {schedule}\n"
            "💰 <b>Kaffaltii Ji'aa:</b> <b>{fee}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🏛️ <b>Herreega Kaffaltii Akaadaamii:</b>\n"
            "• <b>Baankii Daldala Itoophiyaa (CBE):</b>\n"
            "  Lakkoofsa: <code>1000234567890</code>\n"
            "  Maqaa: <i>Online Quran Academy</i>\n\n"
            "• <b>Telebirr:</b>\n"
            "  Lakkoofsa: <code>0911223344</code>\n"
            "  Maqaa: <i>Online Quran Academy</i>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📸 <b>Tarkaanfii Dhumaa:</b>\n"
            "Maaloo kaffaltii raawwadhaatii <b>suuraa nagahee kaffaltii</b> ergaatii galmee xumuraa:"
        ),
        "ar": (
            "💳 <b>ملخص التسجيل وتعليمات الدفع</b>\n\n"
            "👤 <b>الطالب:</b> {full_name}\n"
            "📚 <b>الدورة:</b> {program_name}\n"
            "📍 <b>الموقع:</b> {location}\n"
            "📞 <b>الهاتف:</b> {phone}\n"
            "📅 <b>الوقت المفضل:</b> {schedule}\n"
            "💰 <b>الرسوم الشهرية:</b> <b>{fee}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🏛️ <b>الحسابات الرسمية المعتمدة:</b>\n"
            "• <b>البنك التجاري الإثيوبي (CBE):</b>\n"
            "  رقم الحساب: <code>1000234567890</code>\n"
            "  الاسم: <i>Online Quran Academy</i>\n\n"
            "• <b>تيلي بير (Telebirr):</b>\n"
            "  الرقم: <code>0911223344</code>\n"
            "  الاسم: <i>Online Quran Academy</i>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📸 <b>الخطوة الأخيرة:</b>\n"
            "يُرجى إتمام التحويل وإرسال <b>صورة إيصال الدفع</b> أدناه لإتمام تسجيلكم:"
        ),
    },
    "reg_receipt_prompt": {
        "en": (
            "📸 <b>Payment Receipt Required</b>\n\n"
            "Please send a <b>photo or screenshot</b> of your payment receipt to complete your registration.\n\n"
            "<i>(Tap below if you wish to cancel)</i>"
        ),
        "am": (
            "📸 <b>የክፍያ ደረሰኝ ያስፈልጋል</b>\n\n"
            "ምዝገባዎን ለማጠናቀቅ እባክዎ የከፈሉበትን <b>የደረሰኝ ፎቶ ወይም ስክሪንሾት</b> ይላኩ።\n\n"
            "<i>(መሰረዝ ከፈለጉ ከታች ይጫኑ)</i>"
        ),
        "om": (
            "📸 <b>Nagahee Kaffaltii Barbaachisa</b>\n\n"
            "Galmee xumuruuf maaloo <b>suuraa ykn screenshot nagahee kaffaltii</b> ergaa.\n\n"
            "<i>(Haqquuf kan armaan gadii tuqaa)</i>"
        ),
        "ar": (
            "📸 <b>إيصال الدفع مطلوب</b>\n\n"
            "يُرجى إرسال <b>صورة أو لقطة شاشة لإيصال السداد</b> لإكمال عملية التسجيل.\n\n"
            "<i>(اضغط أدناه إذا كنت ترغب بإلغاء التسجيل)</i>"
        ),
    },
    "reg_success": {
        "en": (
            "🎉 <b>Registration Submitted Successfully!</b>\n\n"
            "Your Registration ID: <code>{reg_id}</code>\n"
            "Selected Program: <b>{program_name}</b>\n\n"
            "✅ Your payment receipt has been received and submitted for administrator verification.\n"
            "The academy will confirm your class schedule and contact you shortly.\n\n"
            "Barakallahu Feekum!"
        ),
        "am": (
            "🎉 <b>ምዝገባዎ በተሳካ ሁኔታ ተጠናቋል!</b>\n\n"
            "የምዝገባ መታወቂያዎ (ID)፡ <code>{reg_id}</code>\n"
            "የተመረጠው ኮርስ፡ <b>{program_name}</b>\n\n"
            "✅ የከፈሉበት ደረሰኝ ደርሶናል፤ ለአስተዳዳሪው እንዲረጋገጥ ተልኳል።\n"
            "አካዳሚው ክፍያውን አረጋግጦ የክፍል ፕሮግራምዎን በቅርቡ ያሳውቅዎታል።\n\n"
            "ባረከላሁ ፊኩም!"
        ),
        "om": (
            "🎉 <b>Galmeen Keessan Milkaa'inaan Xumurameera!</b>\n\n"
            "Eenyummaa Galmee (ID): <code>{reg_id}</code>\n"
            "Koorsii Filatame: <b>{program_name}</b>\n\n"
            "✅ Nagaheen kaffaltii keessanii qaqqabee mirkaneessaaf dhiyaateera.\n"
            "Akaadaamiin kaffaltii mirkaneessee sagantaa daree isin beeksisa.\n\n"
            "Baarakallaahu Fiikum!"
        ),
        "ar": (
            "🎉 <b>تم إرسال طلب التسجيل بنجاح!</b>\n\n"
            "رقم التسجيل: <code>{reg_id}</code>\n"
            "البرنامج: <b>{program_name}</b>\n\n"
            "✅ تم استلام إيصال الدفع وجارٍ مراجعته واعتماده من قبل الإدارة.\n"
            "ستتواصل معكم الأكاديمية قريباً لتأكيد المواعيد والخطوات التالية.\n\n"
            "بارك الله فيكم وجزاكم خيراً!"
        ),
    },

    # -----------------------------------------------------------------------
    # Monthly Fees Screen
    # -----------------------------------------------------------------------
    "fees_title": {
        "en": "💰 <b>Academy Monthly Fees</b>\n\n",
        "am": "💰 <b>የአካዳሚው ወርሃዊ ክፍያዎች</b>\n\n",
        "om": "💰 <b>Kaffaltii Ji'aa Akaadaamii</b>\n\n",
        "ar": "💰 <b>الرسوم والاشتراكات الشهرية بالأكاديمية</b>\n\n",
    },
    "fees_contact": {
        "en": "Contact the Academy",
        "am": "አካዳሚውን ያነጋግሩ",
        "om": "Akaadaamii Qunnamaa",
        "ar": "تواصل مع الأكاديمية",
    },

    # -----------------------------------------------------------------------
    # Help & Contact Screen
    # -----------------------------------------------------------------------
    "help_title": {
        "en": (
            "❓ <b>Help & Contact Academy Administration</b>\n\n"
            "Need assistance or have inquiries about our programs?\n\n"
            "📞 <b>Phone / WhatsApp:</b> +251 91 122 3344\n"
            "✉️ <b>Email:</b> support@quranacademy.example.com\n"
            "🌐 <b>Website:</b> https://quranacademy.example.com\n\n"
            "<i>You can also contact our administrators directly via @xmzgebaadminbot.</i>"
        ),
        "am": (
            "❓ <b>እርዳታ እና የአካዳሚው አድራሻ</b>\n\n"
            "ጥያቄ ወይም ተጨማሪ መረጃ ይፈልጋሉ?\n\n"
            "📞 <b>ስልክ / WhatsApp:</b> +251 91 122 3344\n"
            "✉️ <b>ኢሜይል:</b> support@quranacademy.example.com\n"
            "🌐 <b>ድህረ ገጽ:</b> https://quranacademy.example.com\n\n"
            "<i>እንዲሁም አስተዳዳሪዎችን በቀጥታ በ @xmzgebaadminbot ማግኘት ይችላሉ።</i>"
        ),
        "om": (
            "❓ <b>Gargaarsa fi Qunnamtii Akaadaamii</b>\n\n"
            "Gargaarsa ykn gaaffii dabalataa qabduu?\n\n"
            "📞 <b>Bilbila / WhatsApp:</b> +251 91 122 3344\n"
            "✉️ <b>Iimeelii:</b> support@quranacademy.example.com\n"
            "🌐 <b>Marsariitii:</b> https://quranacademy.example.com\n\n"
            "<i>Akkasumas kallattiin @xmzgebaadminbot fayyadamuun nu qunnamuu dandeessu.</i>"
        ),
        "ar": (
            "❓ <b>المساعدة والتواصل مع إدارة الأكاديمية</b>\n\n"
            "هل لديك استفسار أو تحتاج إلى مساعدة؟\n\n"
            "📞 <b>هاتف / واتساب:</b> +251 91 122 3344\n"
            "✉️ <b>البريد الإلكتروني:</b> support@quranacademy.example.com\n"
            "🌐 <b>الموقع الإلكتروني:</b> https://quranacademy.example.com\n\n"
            "<i>يمكنكم أيضاً التواصل مع الإدارة مباشرة عبر @xmzgebaadminbot.</i>"
        ),
    },

    # -----------------------------------------------------------------------
    # My Profile Screen
    # -----------------------------------------------------------------------
    "profile_not_registered": {
        "en": (
            "👤 <b>Student Profile</b>\n\n"
            "You are not registered yet.\n\n"
            "Tap <b>'Register as a Student'</b> to begin your Quran learning journey!"
        ),
        "am": (
            "👤 <b>የተማሪ መገለጫ</b>\n\n"
            "እስካሁን አልተመዘገቡም።\n\n"
            "የቁርኣን ትምህርትዎን ለመጀመር <b>'በተማሪነት ይመዝገቡ'</b> የሚለውን ይጫኑ!"
        ),
        "om": (
            "👤 <b>Piroofayilii Barataa</b>\n\n"
            "Hanga ammaatti hin galmoofne.\n\n"
            "Barnoota Qur'aanaa jalqabuuf <b>'Barataa Ta'aa Galmaa'aa'</b> kan jedhu tuqaa!"
        ),
        "ar": (
            "👤 <b>الملف الشخصي للطالب</b>\n\n"
            "لم تقم بالتسجيل بعد.\n\n"
            "اضغط على <b>'التسجيل كطالب'</b> لبدء رحلتك في تعلّم القرآن الكريم!"
        ),
    },
    "reg_cancelled": {
        "en": "Registration cancelled. You can register anytime from the main menu.",
        "am": "ምዝገባው ተሰርዟል። በማንኛውም ጊዜ ከዋናው ማውጫ መመዝገብ ይችላሉ።",
        "om": "Galmeen haqameera. Yeroo kamiyyuu baafata guddaa irraa galmaa'uu dandeessu.",
        "ar": "تم إلغاء التسجيل. يمكنك التسجيل في أي وقت من القائمة الرئيسية.",
    },
}


def t(key: str, lang: str | None = None, **kwargs) -> str:
    """Retrieve localized string by key with fallback to English."""
    if not lang or lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    category = STRINGS.get(key, {})
    text = category.get(lang) or category.get("en", key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def get_user_lang(telegram_user_id: int | None) -> str:
    """Get the saved language code for a user."""
    return db.get_user_language(telegram_user_id)
