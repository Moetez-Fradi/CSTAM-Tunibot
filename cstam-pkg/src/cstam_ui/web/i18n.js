// Customer page wording in English, French and Arabic (right-to-left).
// t(key, vars) fills {name} placeholders; plural-aware strings are functions.
'use strict';

const I18N = (() => {
  const LANGS = {
    en: { short: 'EN', name: 'English', dir: 'ltr' },
    fr: { short: 'FR', name: 'Français', dir: 'ltr' },
    ar: { short: 'ع', name: 'العربية', dir: 'rtl' },
  };

  const STRINGS = {
    en: {
      language: 'Language',
      theme: 'Switch light or dark theme',
      loading: 'Loading the menu…',
      offline: 'The robot server isn’t reachable. Your order is safe; this page reconnects by itself.',
      page_title: 'Order to {place}',
      table: 'Table {n}', terrace: 'Terrace {n}',
      zone_terrace: 'terrace', zone_room: 'dining room', zone_upstairs: 'upstairs',
      floor_name: 'Floor {n}', elevator_way: 'The robot is taking the elevator up to you.',
      unknown_table_title: 'We can’t find that table',
      unknown_table_text: 'There is no table called “{name}”. Pick yours below, or scan the code on your table again.',
      choose_title: 'Where are you sitting?',
      choose_text: 'Pick your table and the robot will bring your order there.',
      tables: 'Tables',
      intro_room: 'Choose what you’d like and the robot brings it to your table in the dining room.',
      intro_terrace: 'Choose what you’d like and the robot brings it to your table on the terrace.',
      intro_upstairs: 'Choose what you’d like and the robot brings it up to your table by the elevator.',
      quantity: '{item} quantity', remove_one: 'Remove one {item}', add_one: 'Add one {item}', add: 'Add',
      send: ({ n, place }) => `Send ${n} item${n > 1 ? 's' : ''} to ${place}`,
      empty_cart: 'Add something to order',
      note_label: 'Note for the kitchen', note_placeholder: 'Allergies, no sugar, extra napkins…',
      voice_section: 'Order in your own words',
      voice_label_speak: 'Say or type your order',
      voice_label_type: 'Type your order in your own words',
      voice_reading: 'Reading your order…',
      voice_none: 'No menu item recognised in “{text}”. Try “two espressos and a brik”.',
      voice_added: 'Added {items}. Check the order below, then send it.',
      voice_other_before: ' You mentioned ', voice_other_after: '; this page orders to {place}.',
      voice_speak: 'Speak your order', voice_language: 'Voice language', voice_listening: 'Listening…',
      mic_blocked: 'Microphone access is blocked. Type your order instead.',
      mic_network: 'Voice needs an internet connection. Type your order instead.',
      mic_silence: 'I didn’t hear anything. Tap the microphone and speak.',
      mic_stopped: 'Voice input stopped. Type your order instead.',
      map: 'Map of the restaurant with the robot and your table',
      progress: 'Order progress',
      steps: ['Order received', 'Collecting from the kitchen', 'On the way to you', 'At your table', 'Delivered'],
      eta_kitchen: 'until it reaches the kitchen', eta_you: 'until it reaches you',
      to_drive: 'still to drive', before_leaving: 'before the robot moves on',
      lost_title: 'We can’t find this order',
      lost_text: 'The robot was restarted and no longer knows it. Please order again or ask a member of staff.',
      ahead: ({ n }) => `${n} order${n > 1 ? 's' : ''} ahead of yours`,
      next: 'Your order is next',
      vip_first: 'Welcome back! As our VIP guest, your order goes first.',
      charging: 'The robot is charging and sets off again at 80% battery.',
      interrupted: 'The robot had to return to its dock and will bring your order first.',
      preparing: 'The kitchen is preparing it. You can still cancel.',
      on_way: 'Your order is on its way', keep_clear: 'Please keep the path to your table clear.',
      collecting: 'The robot is collecting your order', at_hatch: 'It picks it up at the kitchen hatch.',
      arrived: 'Your order has arrived',
      take_items: 'Take your items from the robot, then tap the button so it can go.',
      enjoy: 'Enjoy your meal', gone_back: 'The robot has gone back to its dock.',
      cancelled: 'Order cancelled', nothing_brought: 'Nothing will be brought to your table.',
      failed: 'The robot couldn’t reach your table',
      staff_brings: 'A member of staff will bring your order instead.',
      received: 'Order received',
      got_it: 'I’ve got my order', cancel: 'Cancel order', cancel_again: 'Tap again to cancel the order',
      order_more: 'Order something else', cancelled_toast: 'Order cancelled',
      note: 'Note: {note}', total: 'Total', order_id: 'Order {id}',
      min: 'min', sec: 's', currency: '{amount} TND',
    },
    fr: {
      language: 'Langue',
      theme: 'Passer en thème clair ou sombre',
      loading: 'Chargement du menu…',
      offline: 'Le serveur du robot est injoignable. Votre commande est conservée ; la page se reconnecte toute seule.',
      page_title: 'Commander à la {place}',
      table: 'Table {n}', terrace: 'Terrasse {n}',
      zone_terrace: 'terrasse', zone_room: 'salle', zone_upstairs: 'étage',
      floor_name: 'Niveau {n}', elevator_way: 'Le robot prend l’ascenseur pour monter jusqu’à vous.',
      unknown_table_title: 'Table introuvable',
      unknown_table_text: 'Aucune table ne s’appelle « {name} ». Choisissez la vôtre ci-dessous ou scannez à nouveau le code sur votre table.',
      choose_title: 'Où êtes-vous assis ?',
      choose_text: 'Choisissez votre table et le robot vous y apportera votre commande.',
      tables: 'Tables',
      intro_room: 'Choisissez ce qui vous fait envie : le robot l’apporte à votre table, en salle.',
      intro_terrace: 'Choisissez ce qui vous fait envie : le robot l’apporte à votre table, en terrasse.',
      intro_upstairs: 'Choisissez ce qui vous fait envie : le robot monte l’apporter à votre table par l’ascenseur.',
      quantity: 'Quantité de {item}', remove_one: 'Retirer un {item}', add_one: 'Ajouter un {item}', add: 'Ajouter',
      send: ({ n, place }) => `Envoyer ${n} article${n > 1 ? 's' : ''} à la ${place}`,
      empty_cart: 'Ajoutez quelque chose à commander',
      note_label: 'Note pour la cuisine', note_placeholder: 'Allergies, sans sucre, serviettes en plus…',
      voice_section: 'Commander avec vos propres mots',
      voice_label_speak: 'Dites ou écrivez votre commande',
      voice_label_type: 'Écrivez votre commande avec vos propres mots',
      voice_reading: 'Lecture de votre commande…',
      voice_none: 'Aucun plat reconnu dans « {text} ». Essayez « deux cafés et une citronnade ».',
      voice_added: 'Ajouté : {items}. Vérifiez la commande ci-dessous, puis envoyez-la.',
      voice_other_before: ' Vous avez mentionné la ', voice_other_after: ' ; cette page commande pour la {place}.',
      voice_speak: 'Dicter votre commande', voice_language: 'Langue de la dictée', voice_listening: 'J’écoute…',
      mic_blocked: 'L’accès au micro est bloqué. Écrivez plutôt votre commande.',
      mic_network: 'La dictée a besoin d’Internet. Écrivez plutôt votre commande.',
      mic_silence: 'Je n’ai rien entendu. Touchez le micro et parlez.',
      mic_stopped: 'La dictée s’est arrêtée. Écrivez plutôt votre commande.',
      map: 'Plan du restaurant avec le robot et votre table',
      progress: 'Suivi de la commande',
      steps: ['Commande reçue', 'Retrait en cuisine', 'En route vers vous', 'À votre table', 'Livrée'],
      eta_kitchen: 'avant d’arriver en cuisine', eta_you: 'avant d’arriver chez vous',
      to_drive: 'encore à parcourir', before_leaving: 'avant que le robot ne reparte',
      lost_title: 'Commande introuvable',
      lost_text: 'Le robot a redémarré et ne la connaît plus. Commandez à nouveau ou adressez-vous au personnel.',
      ahead: ({ n }) => `${n} commande${n > 1 ? 's' : ''} avant la vôtre`,
      next: 'Votre commande est la prochaine',
      vip_first: 'Bon retour parmi nous ! En tant qu’invité VIP, votre commande passe en premier.',
      charging: 'Le robot se recharge et repart à 80 % de batterie.',
      interrupted: 'Le robot a dû retourner à sa base et apportera votre commande en premier.',
      preparing: 'La cuisine la prépare. Vous pouvez encore annuler.',
      on_way: 'Votre commande arrive', keep_clear: 'Merci de laisser le passage libre jusqu’à votre table.',
      collecting: 'Le robot récupère votre commande', at_hatch: 'Il la prend au passe-plat de la cuisine.',
      arrived: 'Votre commande est arrivée',
      take_items: 'Prenez vos articles sur le robot, puis touchez le bouton pour qu’il reparte.',
      enjoy: 'Bon appétit', gone_back: 'Le robot est retourné à sa base.',
      cancelled: 'Commande annulée', nothing_brought: 'Rien ne sera apporté à votre table.',
      failed: 'Le robot n’a pas pu atteindre votre table',
      staff_brings: 'Un membre du personnel vous apportera votre commande.',
      received: 'Commande reçue',
      got_it: 'J’ai ma commande', cancel: 'Annuler la commande', cancel_again: 'Touchez encore pour annuler',
      order_more: 'Commander autre chose', cancelled_toast: 'Commande annulée',
      note: 'Note : {note}', total: 'Total', order_id: 'Commande {id}',
      min: 'min', sec: 's', currency: '{amount} DT',
    },
    ar: {
      language: 'اللغة',
      theme: 'التبديل بين الوضع الفاتح والداكن',
      loading: 'جارٍ تحميل القائمة…',
      offline: 'تعذّر الاتصال بخادم الروبوت. طلبك محفوظ، وستُعيد الصفحة الاتصال تلقائيًا.',
      page_title: 'اطلب إلى {place}',
      table: 'طاولة {n}', terrace: 'التراس {n}',
      zone_terrace: 'التراس', zone_room: 'القاعة', zone_upstairs: 'الطابق العلوي',
      floor_name: 'الطابق {n}', elevator_way: 'يستقل الروبوت المصعد ليصعد إليك.',
      unknown_table_title: 'لم نجد هذه الطاولة',
      unknown_table_text: 'لا توجد طاولة باسم «{name}». اختر طاولتك من القائمة أدناه، أو امسح الرمز الموجود على طاولتك مجددًا.',
      choose_title: 'أين تجلس؟',
      choose_text: 'اختر طاولتك وسيحضر الروبوت طلبك إليها.',
      tables: 'الطاولات',
      intro_room: 'اختر ما تشتهيه وسيحضره الروبوت إلى طاولتك في القاعة.',
      intro_terrace: 'اختر ما تشتهيه وسيحضره الروبوت إلى طاولتك في التراس.',
      intro_upstairs: 'اختر ما تشتهيه وسيصعد الروبوت بالمصعد ليحضره إلى طاولتك.',
      quantity: 'كمية {item}', remove_one: 'إزالة واحد من {item}', add_one: 'إضافة واحد من {item}', add: 'أضف',
      send: ({ n, place }) => `أرسل ${n === 1 ? 'صنفًا واحدًا' : n === 2 ? 'صنفين' : n <= 10 ? `${n} أصناف` : `${n} صنفًا`} إلى ${place}`,
      empty_cart: 'أضف شيئًا لتطلبه',
      note_label: 'ملاحظة للمطبخ', note_placeholder: 'حساسية، بدون سكر، مناديل إضافية…',
      voice_section: 'اطلب بكلماتك',
      voice_label_speak: 'قل طلبك أو اكتبه (بالفرنسية أو الإنجليزية)',
      voice_label_type: 'اكتب طلبك بكلماتك (بالفرنسية أو الإنجليزية)',
      voice_reading: 'جارٍ قراءة طلبك…',
      voice_none: 'لم نتعرّف على أي صنف في «{text}». جرّب «deux cafés et une citronnade».',
      voice_added: 'تمت إضافة {items}. راجع الطلب أدناه ثم أرسله.',
      voice_other_before: ' ذكرتَ ', voice_other_after: '؛ هذه الصفحة تطلب إلى {place}.',
      voice_speak: 'قل طلبك', voice_language: 'لغة الإملاء الصوتي', voice_listening: 'أستمع…',
      mic_blocked: 'الوصول إلى الميكروفون محظور. اكتب طلبك بدلًا من ذلك.',
      mic_network: 'يحتاج الإملاء الصوتي إلى الإنترنت. اكتب طلبك بدلًا من ذلك.',
      mic_silence: 'لم أسمع شيئًا. المس الميكروفون وتحدّث.',
      mic_stopped: 'توقّف الإملاء الصوتي. اكتب طلبك بدلًا من ذلك.',
      map: 'مخطط المطعم مع الروبوت وطاولتك',
      progress: 'مراحل الطلب',
      steps: ['تم استلام الطلب', 'الاستلام من المطبخ', 'في الطريق إليك', 'عند طاولتك', 'تم التوصيل'],
      eta_kitchen: 'حتى يصل إلى المطبخ', eta_you: 'حتى يصل إليك',
      to_drive: 'المسافة المتبقية', before_leaving: 'قبل أن يغادر الروبوت',
      lost_title: 'لم نجد هذا الطلب',
      lost_text: 'أُعيد تشغيل الروبوت ولم يعد يعرف هذا الطلب. يرجى الطلب من جديد أو التوجّه إلى أحد الموظفين.',
      ahead: ({ n }) => (n === 1 ? 'طلب واحد قبل طلبك' : n === 2 ? 'طلبان قبل طلبك' : `${n} طلبات قبل طلبك`),
      next: 'طلبك هو التالي',
      vip_first: 'أهلًا بعودتك! بصفتك ضيفًا مميزًا، يُقدَّم طلبك أولًا.',
      charging: 'الروبوت قيد الشحن وسينطلق مجددًا عند 80٪ من البطارية.',
      interrupted: 'اضطر الروبوت إلى العودة إلى محطته وسيحضر طلبك أولًا.',
      preparing: 'المطبخ يحضّر طلبك. ما زال بإمكانك الإلغاء.',
      on_way: 'طلبك في الطريق', keep_clear: 'يرجى إبقاء الممر إلى طاولتك خاليًا.',
      collecting: 'الروبوت يستلم طلبك', at_hatch: 'يستلمه من نافذة المطبخ.',
      arrived: 'وصل طلبك',
      take_items: 'خذ أصنافك من الروبوت، ثم المس الزر ليتمكّن من المغادرة.',
      enjoy: 'بالهناء والشفاء', gone_back: 'عاد الروبوت إلى محطته.',
      cancelled: 'تم إلغاء الطلب', nothing_brought: 'لن يُحضَر شيء إلى طاولتك.',
      failed: 'تعذّر على الروبوت الوصول إلى طاولتك',
      staff_brings: 'سيحضر أحد الموظفين طلبك.',
      received: 'تم استلام الطلب',
      got_it: 'استلمت طلبي', cancel: 'إلغاء الطلب', cancel_again: 'المس مرة أخرى لإلغاء الطلب',
      order_more: 'اطلب شيئًا آخر', cancelled_toast: 'تم إلغاء الطلب',
      note: 'ملاحظة: {note}', total: 'المجموع', order_id: 'الطلب {id}',
      min: 'د', sec: 'ث', currency: '{amount} د.ت',
    },
  };

  // Messages the server sends, translated when known.
  const SERVER = {
    fr: {
      'the robot is offline': 'Le robot est hors ligne',
      'this table already has an order on the way': 'Cette table a déjà une commande en cours',
      'the robot is not at your table yet': 'Le robot n’est pas encore à votre table',
      'the robot did not answer; try again': 'Le robot n’a pas répondu ; réessayez',
      'No connection to the robot server. Check the Wi-Fi and try again.':
        'Pas de connexion au serveur du robot. Vérifiez le Wi-Fi et réessayez.',
    },
    ar: {
      'the robot is offline': 'الروبوت غير متصل',
      'this table already has an order on the way': 'لهذه الطاولة طلب قيد التوصيل بالفعل',
      'the robot is not at your table yet': 'لم يصل الروبوت إلى طاولتك بعد',
      'the robot did not answer; try again': 'لم يستجب الروبوت؛ حاول مرة أخرى',
      'No connection to the robot server. Check the Wi-Fi and try again.':
        'لا يوجد اتصال بخادم الروبوت. تحقّق من شبكة Wi-Fi وحاول مرة أخرى.',
    },
  };

  const KEY = 'cstam.lang';
  const read = () => { try { return localStorage.getItem(KEY); } catch { return null; } };
  const browser = (navigator.languages || [navigator.language || 'en']).map((l) => l.slice(0, 2))
    .find((l) => LANGS[l]);
  let lang = LANGS[read()] ? read() : (browser || 'en');

  function apply() {
    document.documentElement.lang = lang;
    document.documentElement.dir = LANGS[lang].dir;
  }
  apply();

  function t(key, vars = {}) {
    const value = STRINGS[lang][key] ?? STRINGS.en[key] ?? key;
    if (typeof value === 'function') return value(vars);
    if (typeof value !== 'string') return value;
    return value.replace(/\{(\w+)\}/g, (_, name) => (vars[name] ?? ''));
  }

  function set(next) {
    if (!LANGS[next] || next === lang) return;
    lang = next;
    try { localStorage.setItem(KEY, next); } catch { /* private mode */ }
    apply();
    window.dispatchEvent(new Event('cstam-lang'));
  }

  // table_3 -> "Table 3" / "Table 3" / "طاولة 3"
  function place(name) {
    const match = /^(table|terrace)_(\d+)$/.exec(name || '');
    return match ? t(match[1], { n: match[2] }) : (name || '').replace(/_/g, ' ');
  }

  const itemName = (item) => (item && ((item.names || {})[lang] || item.name)) || '';
  const server = (message) => (SERVER[lang] || {})[message] || message;

  return { LANGS, t, set, place, itemName, server, lang: () => lang };
})();
