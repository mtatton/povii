#version 3.7;

global_settings {
  assumed_gamma 1.0
  max_trace_level 40
}

background { color rgb <0.004, 0.008, 0.010> }

camera {
  location <0, 0.15, -4.2>
  look_at  <0, 0.05, 0>
  angle 34
}

light_source { <-8, 10, -10> color rgb <1.7, 1.7, 1.7> }
light_source { < 8,  6,  -4> color rgb <0.60, 0.95, 1.25> }
light_source { < 0, 14,   8> color rgb <0.25, 0.55, 0.85> }

#declare FuzzyRactalCyanGlass =
material {
  texture {
    pigment {
      average
      pigment_map {
        [1
          granite
          turbulence 2.2
          octaves 10
          omega 0.55
          lambda 2.15
          color_map {
            [0.00 color rgbt <0.00, 0.38, 0.52, 0.965>]
            [0.18 color rgbt <0.02, 0.62, 0.82, 0.940>]
            [0.45 color rgbt <0.06, 0.95, 0.99, 0.885>]
            [0.72 color rgbt <0.02, 0.60, 0.80, 0.945>]
            [1.00 color rgbt <0.10, 1.00, 0.96, 0.860>]
          }
          scale 0.45
        ]
        [1
          wrinkles
          turbulence 1.4
          octaves 8
          lambda 2.05
          omega 0.60
          color_map {
            [0.00 color rgbt <0.00, 0.35, 0.50, 0.985>]
            [0.50 color rgbt <0.08, 0.90, 0.98, 0.910>]
            [1.00 color rgbt <0.02, 0.60, 0.78, 0.970>]
          }
          scale 0.22
        ]
        [1
          bozo
          turbulence 1.8
          octaves 7
          lambda 2.20
          omega 0.55
          color_map {
            [0.00 color rgbt <0.00, 0.30, 0.45, 0.990>]
            [0.35 color rgbt <0.03, 0.70, 0.86, 0.945>]
            [0.65 color rgbt <0.10, 1.00, 0.98, 0.900>]
            [1.00 color rgbt <0.02, 0.55, 0.75, 0.965>]
          }
          scale 0.10
        ]
      }
    }
    finish {
      diffuse 0.01
      ambient 0
      specular 0.90
      roughness 0.004
      reflection 0.10
      conserve_energy
    }
    normal {
      average
      normal_map {
        [1 bumps 0.18 scale 0.055]
        [1 wrinkles 0.35 scale 0.12 turbulence 1.2]
        [1 granite 0.55 scale 0.20 turbulence 1.0]
      }
    }
  }
  interior {
    ior 1.54
    caustics 1.0
    fade_distance 2.0
    fade_power 1.25
    fade_color <0.01, 0.75, 0.85>
  }
}

#declare BoxSize = 1.25;
#declare BoxRot  = <7, -22, 0>;

box {
  <-BoxSize, -BoxSize, -BoxSize>, <BoxSize, BoxSize, BoxSize>
  material { FuzzyRactalCyanGlass }
  hollow
  rotate BoxRot
}

sphere {
  <0,0,0>, 0.001
  pigment { color rgbt 1 }
  finish { ambient 0 diffuse 0 }
  no_shadow
}