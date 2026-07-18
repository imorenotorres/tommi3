# Sonic Pi Reference — Valid Resources

## Synths (use_synth :name)

### Melodic / Harmonic
- :beep — Pure sine wave, clean tone
- :sine — Alias for beep
- :saw — Raw sawtooth, bright and buzzy
- :pulse — Pulse wave with adjustable width
- :square — Square wave, hollow digital sound
- :triangle — Soft, mellow triangle wave
- :dull_bell — Soft bell tone
- :pretty_bell — Bright bell tone
- :fm — FM synthesis, good for electric piano and bells
- :tb303 — Classic acid bass synthesizer, great for bass lines
- :prophet — Warm detuned analog-style synth
- :zawa — Metallic, evolving pad sound
- :supersaw — Thick detuned saws, good for trance/EDM leads
- :hoover — Classic rave hoover sound
- :dark_ambience — Dark atmospheric pad
- :growl — Aggressive growling bass
- :hollow — Soft airy pad, good for ambient
- :piano — Built-in synth piano (alias for synth_piano)
- :pluck — Plucked string sound (alias for synth_pluck)

### Detuned variants
- :dsaw — Detuned saw (alias for detuned_saw)
- :dpulse — Detuned pulse (alias for detuned_pulse)
- :dtri — Detuned triangle (alias for detuned_triangle)

### Modulated variants
- :mod_saw — Modulated sawtooth
- :mod_dsaw — Modulated detuned sawtooth
- :mod_sine — Modulated sine
- :mod_tri — Modulated triangle
- :mod_pulse — Modulated pulse

### Noise
- :noise — White noise
- :pnoise — Pink noise
- :bnoise — Brown noise
- :gnoise — Grey noise
- :cnoise — Clip noise

## Scales (scale :root, :name)

- :major — Happy, bright (C D E F G A B)
- :minor — Sad, dark (C D Eb F G Ab Bb)
- :pentatonic — Simple, universal (alias for major_pentatonic)
- :major_pentatonic — C D E G A
- :minor_pentatonic — C Eb F G Bb
- :blues — Bluesy, soulful (C Eb F Gb G Bb)
- :dorian — Jazz, funk (C D Eb F G A Bb)
- :mixolydian — Rock, folk (C D E F G A Bb)
- :phrygian — Spanish, flamenco (C Db Eb F G Ab Bb)
- :lydian — Dreamy, bright (C D E F# G A B)
- :locrian — Dark, unstable (C Db Eb F Gb Ab Bb)
- :harmonic_minor — Dramatic, Middle Eastern (C D Eb F G Ab B)
- :melodic_minor_asc — Jazz (C D Eb F G A B)
- :whole — Whole tone, dreamlike (C D E F# G# A#)
- :chromatic — All 12 semitones
- :hungarian_minor — Exotic (C D Eb F# G Ab B)
- :hirajoshi — Japanese (C D Eb G Ab)
- :iwato — Japanese dark (C Db F Gb Bb)
- :kumoi — Japanese (C D Eb G A)
- :pelog — Balinese (C Db Eb G Ab)
- :egyptian — Ancient (C D F G Bb)

## Effects (with_fx :name)

- :reverb — Spacious room sound (room:, mix:)
- :echo — Delayed repetitions (phase:, decay:, mix:)
- :distortion — Gritty overdriven sound (distort:)
- :lpf — Low-pass filter, removes highs (cutoff:)
- :hpf — High-pass filter, removes lows (cutoff:)
- :bpf — Band-pass filter (centre:, res:)
- :flanger — Swooshing jet-like effect (phase:, depth:)
- :wobble — Dubstep-style wobble bass (phase:, cutoff_min:)
- :slicer — Rhythmic chopping (phase:, wave:)
- :panslicer — Stereo panning slicer
- :krush — Bitcrusher effect (gain:, cutoff:)
- :bitcrusher — Reduce bit depth (bits:, sample_rate:)
- :compressor — Dynamic compression (threshold:, slope_above:)
- :whammy — Pitch shifting effect
- :pitch_shift — Pitch shift (pitch:)

## Samples — Drums

### Bass drums
:bd_pure, :bd_808, :bd_zum, :bd_gas, :bd_sone, :bd_haus, :bd_zome, :bd_boom, :bd_klub, :bd_fat, :bd_tek, :bd_ada, :bd_mehackit

### Snares
:sn_dub, :sn_dolf, :sn_zome, :sn_generic

### Hi-hats and cymbals
:hat_snap, :hat_cab, :hat_gem, :hat_metal, :hat_raw, :hat_bdu, :hat_psych

### Drum kit
:drum_heavy_kick, :drum_bass_soft, :drum_bass_hard, :drum_snare_soft, :drum_snare_hard, :drum_cymbal_soft, :drum_cymbal_hard, :drum_cymbal_open, :drum_cymbal_closed, :drum_cymbal_pedal, :drum_tom_lo_soft, :drum_tom_lo_hard, :drum_tom_mid_soft, :drum_tom_mid_hard, :drum_tom_hi_soft, :drum_tom_hi_hard, :drum_splash_soft, :drum_splash_hard, :drum_cowbell, :drum_roll

### Electronic percussion
:elec_triangle, :elec_snare, :elec_lo_snare, :elec_hi_snare, :elec_mid_snare, :elec_cymbal, :elec_soft_kick, :elec_filt_snare, :elec_fuzz_tom, :elec_chime, :elec_bong, :elec_twang, :elec_wood, :elec_pop, :elec_beep, :elec_blip, :elec_blip2, :elec_ping, :elec_bell, :elec_flip, :elec_tick, :elec_hollow_kick, :elec_twip, :elec_plip, :elec_blup

### Percussion
:perc_bell, :perc_bell_2, :perc_snap, :perc_snap2, :perc_swash, :perc_till, :perc_door, :perc_impact_1, :perc_impact_2, :perc_swoosh

## Samples — Melodic

### Bass
:bass_hit_c, :bass_hard_c, :bass_thick_c, :bass_trance_c, :bass_drop_c, :bass_woodsy_c, :bass_voxy_c, :bass_voxy_hit_c, :bass_dnb_f

### Guitar
:guit_harmonics, :guit_e_fifths, :guit_e_slide, :guit_em9

### Ambient
:ambi_soft_buzz, :ambi_swoosh, :ambi_drone, :ambi_glass_hum, :ambi_glass_rub, :ambi_haunted_hum, :ambi_piano, :ambi_lunar_land, :ambi_dark_woosh, :ambi_choir, :ambi_sauna

### Tabla
:tabla_tas1-3, :tabla_ke1-3, :tabla_na, :tabla_na_o, :tabla_tun1-3, :tabla_te1-2, :tabla_te_ne, :tabla_te_m, :tabla_ghe1-8, :tabla_dhec, :tabla_na_s, :tabla_re

### Vinyl
:vinyl_backspin, :vinyl_rewind, :vinyl_scratch, :vinyl_hiss

## Samples — Loops

:loop_industrial, :loop_compus, :loop_amen, :loop_amen_full, :loop_garzul, :loop_mika, :loop_breakbeat, :loop_safari, :loop_tabla, :loop_3dprinter, :loop_drone_g_97, :loop_electric, :loop_perc_1, :loop_perc_2, :loop_weirdo

## Musical Style Reference

### Rock and Roll (BPM: 130-150)
- Drums: shuffle pattern — kick on 1 and 3, snare on 2 and 4, hi-hat in eighth notes or shuffle
- Guitar: power chords or riffs based on E/A/D, synth :saw or :square with :distortion
- Bass: root notes following chord progression, synth :tb303 or :fm
- Key: E major/minor most common
- Typical progression: E-A-B (I-IV-V) or 12-bar blues

### Blues (BPM: 70-100)
- Drums: shuffle feel — triplet-based hi-hat, kick on 1 and 3, snare on 2 and 4
- Piano/Guitar: blues scale, synth :piano or :pluck
- Bass: walking bass line, synth :fm
- Key: C, E, A, G common
- Typical progression: 12-bar blues (I-I-I-I-IV-IV-I-I-V-IV-I-V)

### Jazz (BPM: 100-140)
- Drums: ride cymbal pattern with swing, light kick, snare ghost notes
- Piano: chord voicings (m7, dom7, maj7), synth :piano
- Bass: walking bass (chromatic passing tones), synth :fm
- Key: Dm, Cm, F common
- Typical progression: ii-V-I (Dm-G-C) or blues changes

### Techno (BPM: 125-135)
- Drums: four-on-the-floor kick, offbeat hi-hat, clap on 2 and 4
- Bass: acid bass line, synth :tb303 with :lpf
- Pads: atmospheric, synth :supersaw or :dark_ambience
- Minimal melodic content, emphasis on rhythm and texture

### House (BPM: 118-128)
- Drums: four-on-the-floor kick, offbeat hi-hat, clap/snare on 2 and 4
- Chords: piano or organ stabs, synth :piano
- Bass: simple root notes, synth :fm
- Typical progression: Am-F-C-G or similar

### Ambient (BPM: 50-80)
- No drums or very sparse
- Pads: evolving textures, synth :hollow, :dark_ambience, :zawa
- Melody: sparse generative notes, synth :pluck, :pretty_bell
- Heavy use of :reverb and :echo
- Pentatonic or whole tone scales work well

### Bossa Nova (BPM: 120-140)
- Drums: syncopated pattern — NOT straight, characteristic 3-2 or 2-3 clave feel
- Guitar: nylon-style chords, synth :pluck with :reverb
- Bass: syncopated walking, synth :fm
- Key: Dm, Am, C common
- Typical progression: ii-V-I with m7 chords

### Reggae (BPM: 70-90)
- Drums: one-drop — kick and snare together on beat 3, hi-hat on offbeats
- Skank: offbeat chord stabs, synth :piano or :pluck
- Bass: heavy, melodic, synth :fm or :tb303
- Key: Am, Dm, G common

### Hip-Hop (BPM: 80-100)
- Drums: boom-bap — heavy kick, sharp snare, fast hi-hats
- Bass: deep sub-bass, synth :fm with :lpf
- Samples: vinyl crackle (:vinyl_hiss), vocal chops
- Key: Cm, Am common

### Lo-fi / Chill (BPM: 70-90)
- Drums: soft, muted — :bd_ada, :sn_dub, tape-like
- Piano: jazzy chords with :reverb and :echo, synth :piano
- Bass: warm, round, synth :fm
- Pentatonic or minor scale
- Characteristic: imperfection, warmth, nostalgia

### Drum and Bass (BPM: 160-180)
- Drums: fast breakbeat, syncopated — use :loop_amen or :loop_breakbeat
- Bass: heavy sub-bass, synth :tb303 or :growl
- Pads: atmospheric, synth :hollow or :supersaw

### Funk (BPM: 100-130)
- Drums: syncopated, emphasis on beat 1, ghost notes on snare
- Guitar: choppy staccato, synth :pluck or :saw
- Bass: slap bass, syncopated, synth :fm or :tb303
- Key: E, A, D common
- Heavy use of dorian and mixolydian scales

### Classical / Orchestral (BPM: 60-120)
- Strings: sustained notes, synth :hollow or :dark_ambience
- Piano: synth :piano
- No drums typically
- Major, minor, harmonic_minor scales
- Counterpoint and arpeggios
