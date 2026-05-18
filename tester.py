from tts_arabic import tts
from datetime import datetime
import time
import logging

# Configuration du log
log_filename = f"tts_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Textes (correction : pas de virgule après .strip())
text_moch_machkoul = "هو دُرَّة التراث العالميِّ، وواحد من أفضل كتب الأدب التي تخطَّت أطُر المكان وحدود الزمان لتعيش بيننا حتى اليوم. إنه الكتاب الذي يتناوله الصغار فيستمتعون بحكاياته، والكبار فيستنبطون منه المعاني العديدة والعميقة. وقد اصطبغ الكتاب بصبغات أكثر الحضارات الشرقية ثراءً؛ فهو نتيجة تلاقي ثلاث حضارات هي (الهندية والفارسية والعربية)، والشائع أن مؤلِّفه هو الحكيم الهندي «بيدبا»، وقد كتبه لينصح به الملك «دبشليم»، ثم انتقل الكتاب إلى الأدب الفارسيِّ عندما قام «برزويه» بترجمته إلى «اللغة الفهلوية» وأضاف إليه، وأخيرًا وصل إلى الأدب العربيِّ حينما قام «عبد الله بن المقفع» بترجمته مضيفًا إليه بدوره. ولا شكَّ أن الكتاب يحمل في طياته أبعادًا سياسية واجتماعية؛ جعلته حتى اليوم مادةً للبحث والاستقصاء، وسيظل «كليلة ودمنة» مصدر الإمتاع الأدبيِّ المفضَّل لدى الكبار والصغار."

text_machkoul = """ هُوَ دُرَّةُ التُّرَاثِ الْعَالَمِيِّ، وَوَاحِدٌ مِنْ أَفْضَلِ كُتُبِ الْأَدَبِ الَّتِي تَخَطَّتْ أُطُرَ الْمَكَانِ وَحُدُودَ الزَّمَانِ لِتَعِيشَ بَيْنَنَا حَتَّى الْيَوْمِ. إِنَّهُ الْكِتَابُ الَّذِي يَتَنَاوَلُهُ الصِّغَارُ فَيَسْتَمْتِعُونَ بِحِكَايَاتِهِ، وَالْكِبَارُ فَيَسْتَنْبِطُونَ مِنْهُ الْمَعَانِيَ الْعَدِيدَةَ وَالْعَمِيقَةَ. وَقَدِ اصْطَبَغَ الْكِتَابُ بِصِبْغَاتِ أَكْثَرِ الْحَضَارَاتِ الشَّرْقِيَّةِ ثَرَاءً؛ فَهُوَ نَتِيجَةُ تَلَاقِي ثَلَاثِ حَضَارَاتٍ هِيَ (الْهِنْدِيَّةُ وَالْفَارِسِيَّةُ وَالْعَرَبِيَّةُ)، وَالشَّائِعُ أَنَّ مُؤَلِّفَهُ هُوَ الْحَكِيمُ الْهِنْدِيُّ «بِيدَبَا»، وَقَدْ كَتَبَهُ لِيَنْصَحَ بِهِ الْمَلِكَ «دَبْشَلِيمَ»، ثُمَّ انْتَقَلَ الْكِتَابُ إِلَى الْأَدَبِ الْفَارِسِيِّ عِنْدَمَا قَامَ «بَرْزَوَيْهِ» بِتَرْجَمَتِهِ إِلَى «اللُّغَةِ الْفَهْلَوِيَّةِ» وَأَضَافَ إِلَيْهِ، وَأَخِيرًا وَصَلَ إِلَى الْأَدَبِ الْعَرَبِيِّ حِينَمَا قَامَ «عَبْدُ اللهِ بْنُ الْمُقَفَّعِ» بِتَرْجَمَتِهِ مُضِيفًا إِلَيْهِ بِدَوْرِهِ. وَلَا شَكَّ أَنَّ الْكِتَابَ يَحْمِلُ فِي طَيَّاتِهِ أَبْعَادًا سِيَاسِيَّةً وَاجْتِمَاعِيَّةً؛ جَعَلَتْهُ حَتَّى الْيَوْمِ مَادَّةً لِلْبَحْثِ وَالِاسْتِقْصَاءِ، وَسَيَظَلُّ «كَلِيلَةُ وَدِمْنَةُ» مَصْدَرَ الْإِمْتَاعِ الْأَدَبِيِّ الْمُفَضَّلِ لَدَى الْكِبَارِ وَالصِّغَارِ.""".strip()

# ----- Fonction utilitaire pour éviter la répétition de code -----
def run_tts(text, description, model_id, vocoder_id, speaker=1, pace=1, denoise=0.005, volume=0.9, play=False, pitch_mul=1, pitch_add=0, vowelizer=None, cuda=None, bits=32):
    """Appelle tts, mesure le temps, loggue et sauvegarde le fichier."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename = f"{model_id}_{vocoder_id}_{description}_{timestamp}.wav"
    
    logging.info(f"Début : {description} | modèle={model_id} | vocodeur={vocoder_id}")
    start = time.time()
    
    wave = tts(
        text=text,
        speaker=speaker,
        pace=pace,
        denoise=denoise,
        volume=volume,
        play=play,
        pitch_mul=pitch_mul,
        pitch_add=pitch_add,
        vowelizer=vowelizer,
        model_id=model_id,
        vocoder_id=vocoder_id,
        cuda=cuda,
        save_to=filename,
        bits_per_sample=bits
    )
    
    elapsed = time.time() - start
    logging.info(f"Fin : {elapsed:.2f} secondes -> {filename}")
    print(f"{description:30} | {model_id:10} | {vocoder_id:8} | {elapsed:6.2f} s | fichier: {filename}")
    return elapsed

# ==================== PARTIE 1 : TEXTE AVEC DIACRITIQUES ====================
print("\n" + "="*80)
print("TESTS AVEC DIACRITIQUES (text_machkoul)")
print("="*80)

# fastpitch
run_tts(text_machkoul, "diac_fastpitch", "fastpitch", "hifigan", play=False)
run_tts(text_machkoul, "diac_fastpitch", "fastpitch", "vocos", play=False)
run_tts(text_machkoul, "diac_fastpitch", "fastpitch", "vocos44", play=False)

# mixer128
run_tts(text_machkoul, "diac_mixer128", "mixer128", "hifigan", play=False)
run_tts(text_machkoul, "diac_mixer128", "mixer128", "vocos", play=False)
run_tts(text_machkoul, "diac_mixer128", "mixer128", "vocos44", play=False)

# mixer80
run_tts(text_machkoul, "diac_mixer80", "mixer80", "hifigan", play=False)
run_tts(text_machkoul, "diac_mixer80", "mixer80", "vocos", play=False)
run_tts(text_machkoul, "diac_mixer80", "mixer80", "vocos44", play=False)

# ==================== PARTIE 2 : TEXTE SANS DIACRITIQUES ====================
print("\n" + "="*80)
print("TESTS SANS DIACRITIQUES (text_moch_machkoul)")
print("="*80)

# fastpitch
run_tts(text_moch_machkoul, "plain_fastpitch", "fastpitch", "hifigan", play=False)
run_tts(text_moch_machkoul, "plain_fastpitch", "fastpitch", "vocos", play=False)
run_tts(text_moch_machkoul, "plain_fastpitch", "fastpitch", "vocos44", play=False)

# mixer128
run_tts(text_moch_machkoul, "plain_mixer128", "mixer128", "hifigan", play=False)
run_tts(text_moch_machkoul, "plain_mixer128", "mixer128", "vocos", play=False)
run_tts(text_moch_machkoul, "plain_mixer128", "mixer128", "vocos44", play=False)

# mixer80
run_tts(text_moch_machkoul, "plain_mixer80", "mixer80", "hifigan", play=False)
run_tts(text_moch_machkoul, "plain_mixer80", "mixer80", "vocos", play=False)
run_tts(text_moch_machkoul, "plain_mixer80", "mixer80", "vocos44", play=False)

print(f"\n Tous les tests terminés. Log enregistré dans : {log_filename}")