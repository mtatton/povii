#version 3.7;

global_settings {
  assumed_gamma 1.0
  max_trace_level 20
}

background { color rgb <0.04, 0.06, 0.10> }

camera {
  location <0, 3.25, -9.75>
  look_at  <0, 1.25, 0>
  angle 44
}

light_source {
  <10, 14, -12>
  color rgb <1.0, 0.98, 0.95>
  area_light <2.2,0,0>, <0,0,2.2>, 5, 5
  adaptive 1
  jitter
}

light_source {
  <-7, 7, -3>
  color rgb <0.35, 0.50, 0.75>
  area_light <1.4,0,0>, <0,0,1.4>, 4, 4
  adaptive 1
  jitter
}

light_source { <0, 7, 3> color rgb <0.25, 0.35, 0.45> }

fog {
  distance 24
  color rgb <0.04, 0.06, 0.10>
  fog_type 2
  fog_offset 0.25
  fog_alt 1.7
}

#declare Tex_MarbleSphere = texture {
  pigment {
    marble
    color_map {
      [0.00 rgb <0.10, 0.12, 0.15>]
      [0.35 rgb <0.22, 0.25, 0.30>]
      [0.55 rgb <0.55, 0.58, 0.62>]
      [0.72 rgb <0.85, 0.86, 0.88>]
      [1.00 rgb <0.20, 0.22, 0.26>]
    }
    turbulence 0.8
    omega 0.6
    lambda 2.1
    scale 0.85
    rotate <15, 35, 10>
  }
  normal { bumps 0.22 scale 0.035 }
  finish { diffuse 0.75 specular 0.55 roughness 0.02 reflection 0.10 }
}

#declare Tex_SeaFloor = texture {
  pigment {
    bozo
    color_map {
      [0.00 rgb <0.03, 0.07, 0.12>]
      [0.35 rgb <0.05, 0.12, 0.18>]
      [0.60 rgb <0.02, 0.18, 0.20>]
      [0.78 rgb <0.08, 0.20, 0.25>]
      [1.00 rgb <0.02, 0.08, 0.12>]
    }
    turbulence 0.9
    scale <3.2, 0.25, 3.2>
    translate <0,0,0>
  }
  normal {
    average
    normal_map {
      [1.0 wrinkles 1.1 scale <1.2,0.10,1.2>]
      [0.8 ripples 0.9  frequency 1.2 phase 0.2 scale <1.8,0.08,1.8>]
      [0.7 bumps 0.35 scale 0.12]
    }
  }
  finish { diffuse 0.85 specular 0.35 roughness 0.035 reflection 0.10 }
}

#declare Tex_GlassBumped = texture {
  pigment { color rgbf <0.78, 0.92, 1.0, 0.82> }
  normal {
    average
    normal_map {
      [1.0 bumps 0.55 scale 0.03]
      [0.7 ripples 0.35 frequency 18 phase 0.35 scale 0.015]
    }
  }
  finish {
    diffuse 0.05
    specular 0.95
    roughness 0.004
    reflection 0.10
    conserve_energy
  }
}

#declare Int_Glass = interior {
  ior 1.52
  caustics 0.8
  fade_distance 2.5
  fade_power 2
}

#declare Tex_GlassBumped_Clear = texture { Tex_GlassBumped }
#declare Tex_GlassBumped_Warm  = texture {
  pigment { color rgbf <1.00, 0.85, 0.70, 0.86> }
  normal {
    average
    normal_map {
      [1.0 bumps 0.60 scale 0.032]
      [0.7 ripples 0.30 frequency 16 phase 0.15 scale 0.016]
    }
  }
  finish {
    diffuse 0.04
    specular 0.95
    roughness 0.004
    reflection 0.10
    conserve_energy
  }
}

#declare Tex_InnerGlow = texture {
  pigment { color rgb <0.30, 0.70, 1.00> }
  finish { emission 0.65 diffuse 0 }
}

#declare Tex_EnvRingGlass = texture {
  pigment { color rgbf <0.75, 0.92, 1.0, 0.88> }
  normal { bumps 0.35 scale 0.02 }
  finish { diffuse 0.03 specular 1.0 roughness 0.003 reflection 0.12 conserve_energy }
}

plane {
  y, 0
  texture { Tex_SeaFloor }
}

union {
  // Marble sphere (requested)
  sphere {
    <0, 2.1, 0>, 1.15
    texture { Tex_MarbleSphere }
  }

  // Glass ring (rest = translucent bumped glass)
  torus {
    1.35, 0.085
    rotate <90, 0, 0>
    translate <0, 2.1, 0>
    texture { Tex_EnvRingGlass }
    interior { Int_Glass }
  }

  // Soft inner glow (kept)
  sphere {
    <0, 2.1, 0>, 0.55
    texture { Tex_InnerGlow }
  }

  // Base (translucent bumped glass)
  difference {
    cylinder { <0,0,0>, <0,0.55,0>, 1.9 }
    cylinder { <0,0.12,0>, <0,0.60,0>, 1.55 }
    texture { Tex_GlassBumped_Warm }
    interior { Int_Glass }
  }

  // Accent markers (translucent bumped glass)
  box {
    <-0.10, 0.54, -1.85>, <0.10, 0.80, -1.35>
    texture { Tex_GlassBumped_Clear }
    interior { Int_Glass }
  }
  box {
    <-0.10, 0.54,  1.35>, <0.10, 0.80,  1.85>
    texture { Tex_GlassBumped_Clear }
    interior { Int_Glass }
  }
  box {
    <-1.85, 0.54, -0.10>, <-1.35, 0.80, 0.10>
    texture { Tex_GlassBumped_Clear }
    interior { Int_Glass }
  }
  box {
    < 1.35, 0.54, -0.10>, < 1.85, 0.80, 0.10>
    texture { Tex_GlassBumped_Clear }
    interior { Int_Glass }
  }
}

object {
  union {
    // Thought shards (translucent bumped glass)
    cone { <0,0,0>, 0.0, <0,1.30,0>, 0.35 texture { Tex_GlassBumped_Clear } interior { Int_Glass } }
    cone { <0,0,0>, 0.0, <0,1.10,0>, 0.30 texture { Tex_GlassBumped_Clear } interior { Int_Glass } }
  }
  scale <0.45, 0.8, 0.45>
  rotate <0, 25, 15>
  translate <2.2, 1.0, -0.2>
}

object {
  union {
    cone { <0,0,0>, 0.0, <0,1.40,0>, 0.33 texture { Tex_GlassBumped_Clear } interior { Int_Glass } }
    cone { <0,0,0>, 0.0, <0,1.00,0>, 0.28 texture { Tex_GlassBumped_Clear } interior { Int_Glass } }
  }
  scale <0.42, 0.75, 0.42>
  rotate <0, -35, -10>
  translate <-2.0, 0.95, 0.5>
}

sphere {
  <0, 6.5, 6>, 0.8
  texture {
    pigment { color rgbf <0.35, 0.60, 0.85, 0.90> }
    finish { diffuse 0 emission 0.12 specular 0.2 roughness 0.08 }
  }
  hollow
  interior { ior 1.03 }
}