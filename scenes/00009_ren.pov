#version 3.7;

global_settings {
  assumed_gamma 1.0
  max_trace_level 60
}

background { color rgb <0.004, 0.008, 0.010> }

camera {
  location <0.0, 0.05, -3.35>
  look_at  <0.0, 0.02, 0.0>
  angle 32
}

light_source { <-6, 9, -9> color rgb <2.0, 2.0, 2.0> }
light_source { < 7, 5, -3> color rgb <0.55, 0.95, 1.35> }
light_source { < 0, 12,  7> color rgb <0.25, 0.55, 0.95> }
light_source { < 0,  0, -8> color rgb <0.35, 0.70, 0.85> shadowless }

#declare FuzzyFractalCyanGlass =
material {
  texture {
    pigment {
      average
      pigment_map {
        [1
          granite
          turbulence 2.4
          octaves 10
          omega 0.55
          lambda 2.15
          color_map {
            [0.00 color rgbt <0.00, 0.30, 0.45, 0.975>]
            [0.20 color rgbt <0.02, 0.60, 0.80, 0.945>]
            [0.45 color rgbt <0.10, 0.95, 0.98, 0.900>]
            [0.70 color rgbt <0.02, 0.62, 0.82, 0.945>]
            [1.00 color rgbt <0.10, 1.00, 0.96, 0.885>]
          }
          scale 0.42
        ]
        [1
          wrinkles
          turbulence 1.6
          octaves 8
          lambda 2.05
          omega 0.60
          color_map {
            [0.00 color rgbt <0.00, 0.32, 0.48, 0.985>]
            [0.50 color rgbt <0.10, 0.90, 0.98, 0.925>]
            [1.00 color rgbt <0.02, 0.58, 0.78, 0.975>]
          }
          scale 0.20
        ]
        [1
          bozo
          turbulence 1.9
          octaves 7
          lambda 2.2
          omega 0.55
          color_map {
            [0.00 color rgbt <0.00, 0.28, 0.42, 0.990>]
            [0.35 color rgbt <0.04, 0.70, 0.88, 0.950>]
            [0.65 color rgbt <0.12, 1.00, 0.98, 0.910>]
            [1.00 color rgbt <0.02, 0.54, 0.74, 0.975>]
          }
          scale 0.095
        ]
      }
    }
    finish {
      diffuse 0.02
      ambient 0
      specular 0.95
      roughness 0.0035
      reflection 0.12
      conserve_energy
    }
    normal {
      average
      normal_map {
        [1 bumps   0.22 scale 0.050]
        [1 wrinkles 0.45 scale 0.105 turbulence 1.3]
        [1 granite  0.65 scale 0.190 turbulence 1.1]
      }
    }
  }
  interior {
    ior 1.54
    caustics 1.0
    fade_distance 1.8
    fade_power 1.15
    fade_color <0.02, 0.85, 0.95>
  }
}

#declare BoxSize = 1.12;
#declare BoxRot  = <8, -22, 0>;

union {
  box {
    <-BoxSize, -BoxSize, -BoxSize>, <BoxSize, BoxSize, BoxSize>
    material { FuzzyFractalCyanGlass }
    hollow
    rotate BoxRot
  }

  // Slightly smaller inner shell to strengthen refraction/visibility
  box {
    <-(BoxSize*0.995), -(BoxSize*0.995), -(BoxSize*0.995)>,
    < (BoxSize*0.995),  (BoxSize*0.995),  (BoxSize*0.995)>
    material { FuzzyFractalCyanGlass }
    hollow
    rotate BoxRot
  }
}

sphere {
  <0,0,0>, 0.001
  pigment { color rgbt 1 }
  finish { ambient 0 diffuse 0 }
  no_shadow
}