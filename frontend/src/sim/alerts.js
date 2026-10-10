// WhatsApp-style alert text for the day's top finding.
// In production a Strands agent writes these; these templates are the fallback and the demo copy.
// Marathi and Hindi drafts should be checked by a native speaker before the pitch.
import { fmtDay } from './util.js';

export const LANGS = [
  { id: 'en', label: 'English' },
  { id: 'mr', label: 'मराठी' },
  { id: 'hi', label: 'हिंदी' },
];

export const MESSAGES = {
  ok: {
    en: 'Your borewell is healthy. Water is at {swl} m and the pump has a safe margin until the monsoon.',
    mr: 'तुमची बोअरवेल ठीक आहे. पाणी {swl} मीटरवर आहे आणि पावसाळ्यापर्यंत पंपाला पुरेसा सुरक्षित फरक आहे.',
    hi: 'आपका बोरवेल ठीक है। पानी {swl} मीटर पर है और मानसून तक पंप के लिए पर्याप्त सुरक्षित अंतर है।',
  },
  depl: {
    en: 'Water is falling {rate} m a day. The pump should last until the monsoon, with about {margin} m to spare.',
    mr: 'पाण्याची पातळी दररोज {rate} मीटरने खाली जात आहे. पावसाळ्यापर्यंत पंप चालेल, साधारण {margin} मीटर फरक शिल्लक राहील.',
    hi: 'पानी का स्तर रोज़ {rate} मीटर गिर रहा है। मानसून तक पंप चलेगा, लगभग {margin} मीटर का अंतर बचेगा।',
  },
  forecast: {
    en: 'Water is falling {rate} m a day. At this rate the pump will run dry around {date}. Cut pumping by {cut}% to last until the monsoon.',
    mr: 'पाण्याची पातळी दररोज {rate} मीटरने खाली जात आहे. या वेगाने साधारण {date} रोजी पंप कोरडा चालेल. पावसाळ्यापर्यंत पाणी टिकवण्यासाठी उपसा {cut}% कमी करा.',
    hi: 'पानी का स्तर रोज़ {rate} मीटर गिर रहा है। इसी दर से लगभग {date} को पंप सूखा चलेगा। मानसून तक पानी बचाने के लिए पंपिंग {cut}% कम करें।',
  },
  dry: {
    en: 'Emergency: water reached the pump intake at {time}. The pump was switched off to protect the motor.',
    mr: 'आपत्कालीन सूचना: {time} वाजता पाणी पंपाच्या पातळीपर्यंत खाली गेले. मोटर वाचवण्यासाठी पंप बंद केला आहे.',
    hi: 'आपातकालीन सूचना: {time} बजे पानी पंप के स्तर तक गिर गया। मोटर बचाने के लिए पंप बंद कर दिया गया है।',
  },
  dryon: {
    en: 'Emergency: the pump has been running dry since {time}. Switch it off now to save the motor.',
    mr: 'आपत्कालीन सूचना: {time} पासून पंप कोरडा चालत आहे. मोटर वाचवण्यासाठी पंप लगेच बंद करा.',
    hi: 'आपातकालीन सूचना: {time} से पंप सूखा चल रहा है। मोटर बचाने के लिए पंप तुरंत बंद करें।',
  },
  clog: {
    en: 'The aquifer is fine, but the well itself is clogging. Refill is normal while drawdown has risen {pct}%. Get the borewell cleaned; rationing will not help.',
    mr: 'जलधर ठीक आहे, पण बोअरवेल स्वतः बंद होत आहे. पाणी पुन्हा भरण्याचा वेग सामान्य आहे, पण उपशावेळी पातळी {pct}% जास्त खाली जाते. बोअरवेल स्वच्छ करून घ्या; उपसा कमी करून फायदा होणार नाही.',
    hi: 'जलभृत ठीक है, लेकिन बोरवेल खुद जाम हो रहा है। पानी भरने की दर सामान्य है, पर पंपिंग में स्तर {pct}% ज़्यादा गिरता है। बोरवेल की सफ़ाई कराएँ; पंपिंग घटाने से फ़ायदा नहीं होगा।',
  },
  fracture: {
    en: 'Water has dropped below the fracture at {depth} m that supplied most of your yield. Each run will now draw the level down further. Shorten runs and space them out.',
    mr: 'तुमच्या बोअरवेलला जास्त पाणी देणाऱ्या {depth} मीटरवरील भेगेच्या खाली पाणी गेले आहे. आता प्रत्येक उपशात पातळी जास्त खाली जाईल. उपशाचा वेळ कमी करा आणि दोन उपशांमध्ये अंतर ठेवा.',
    hi: 'पानी {depth} मीटर की उस दरार से नीचे चला गया है जिससे सबसे ज़्यादा पानी आता था। अब हर बार पंप चलाने पर स्तर ज़्यादा गिरेगा। पंपिंग का समय घटाएँ और बीच में अंतर रखें।',
  },
  interf: {
    en: 'Your water level drops while your pump is off, around {time}. A nearby borewell is probably drawing from the same aquifer. Consider agreeing pumping times with your neighbours.',
    mr: 'तुमचा पंप बंद असतानाही साधारण {time} वाजता पाण्याची पातळी खाली जाते. जवळची बोअरवेल याच जलधरातून पाणी उपसत असावी. शेजाऱ्यांसोबत उपशाच्या वेळा ठरवण्याचा विचार करा.',
    hi: 'आपका पंप बंद होने पर भी लगभग {time} बजे पानी का स्तर गिरता है। शायद पास का बोरवेल इसी जलभृत से पानी खींच रहा है। पड़ोसियों के साथ पंपिंग का समय तय करने पर विचार करें।',
  },
  wear: {
    en: 'The pump is delivering less water: drawdown per run is down {pct}% and motor current has dropped. The aquifer looks unchanged. Get the pump serviced.',
    mr: 'पंप कमी पाणी देत आहे: प्रत्येक उपशात पातळी {pct}% कमी खाली जाते आणि मोटरचा विद्युतप्रवाह घटला आहे. जलधर बदललेला नाही. पंपाची दुरुस्ती करून घ्या.',
    hi: 'पंप कम पानी दे रहा है: हर बार स्तर {pct}% कम गिरता है और मोटर का करंट घटा है। जलभृत में बदलाव नहीं दिखता। पंप की सर्विस कराएँ।',
  },
  weak: {
    en: 'Monsoon rain so far is {pct}% of normal and the water level has recovered only to {swl} m. Next summer is high risk. Plan recharge pits and rationing now.',
    mr: 'आतापर्यंतचा पाऊस सरासरीच्या फक्त {pct}% आहे आणि पाण्याची पातळी फक्त {swl} मीटरपर्यंत वर आली आहे. पुढचा उन्हाळा धोकादायक आहे. पुनर्भरणाचे खड्डे आणि उपसा नियोजन आताच करा.',
    hi: 'अब तक की बारिश सामान्य की केवल {pct}% है और पानी का स्तर सिर्फ़ {swl} मीटर तक ही लौटा है। अगली गर्मी जोखिम भरी है। रिचार्ज गड्ढे और पंपिंग की योजना अभी बनाएँ।',
  },
  sensor: {
    en: 'The depth reading has stopped responding to pump runs. This looks like a sensor fault, such as an echo from a pipe joint. The forecast is paused until the sensor is checked.',
    mr: 'पंप चालू-बंद झाला तरी खोलीचे वाचन बदलत नाही. हा सेन्सरमधील दोष दिसतो, उदा. पाईपच्या जोडातून येणारा प्रतिध्वनी. सेन्सर तपासेपर्यंत अंदाज थांबवला आहे.',
    hi: 'पंप चलने-बंद होने पर भी गहराई की रीडिंग नहीं बदल रही। यह सेंसर की खराबी लगती है, जैसे पाइप के जोड़ से आने वाली गूँज। सेंसर जाँचने तक पूर्वानुमान रोका गया है।',
  },
};

export function alertText(finding, lang = 'en') {
  if (!finding || !MESSAGES[finding.msg]) return '';
  const template = MESSAGES[finding.msg][lang] || MESSAGES[finding.msg].en;
  return template.replace(/\{(\w+)\}/g, (_, key) => (key === 'date' ? fmtDay(finding.v[key], lang) : finding.v[key]));
}
