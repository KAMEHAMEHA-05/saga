import soundfile as sf
from kokoro import KPipeline

# Initialize the pipeline ('a' for American English, 'b' for British English)
pipeline = KPipeline(lang_code='a')

text = "Arch Linux makes local machine learning deployment ridiculously clean."

# Generate audio generator (returns graphemes, phonemes, audio tensor)
generator = pipeline(text, voice='af_heart', speed=1.0)

for i, (gs, ps, audio) in enumerate(generator):
    # Save output to wav file
    sf.write(f'output_{i}.wav', audio, 24000)
    print(f"Generated output_{i}.wav successfully.")