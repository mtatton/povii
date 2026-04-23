#version 3.7;

global_settings { assumed_gamma 1.0 }

background { color rgb <0.02, 0.03, 0.04> }

camera {
  location <0, 0, -4.2>
  look_at  <0, 0, 0>
  angle 34
}

light_source { <-6, 7, -7> color rgb <1.2, 1.2, 1.2> }
light_source { < 6, 3, -2> color rgb <0.45, 0.55, 0.7> }
light_source { < 0, 8,  4> color rgb <0.25, 0.35, 0.45> }

#declare FuzzyCyanGlass =
material {
  texture {
    pigment { color rgbt <0.15, 0.95, 0.95, 0.78> }
    finish {
      diffuse 0.05
      specular 0.85 roughness 0.015
      reflection 0.06
      conserve_energy
    }
    normal {
      bumps 0.10 scale 0.08
    }
  }
  interior {
    ior 1.52
    caustics 1.0
    fade_distance 1.8
    fade_power 1.2
    fade_color <0.10, 0.90, 0.90>
  }
}

box {
  <-1.15, -1.15, -1.15>, <1.15, 1.15, 1.15>
  material { FuzzyCyanGlass }
  hollow
  // "stained" and "fractal" feel via turbulence and slight pigment variation
  texture {
    pigment {
      marble
      turbulence 0.9
      octaves 6
      omega 0.55
      lambda 2.1
      color_map {
        [0.00 color rgbt <0.05, 0.70, 0.80, 0.86>]
        [0.35 color rgbt <0.10, 0.95, 0.95, 0.78>]
        [0.65 color rgbt <0.02, 0.55, 0.75, 0.88>]
        [1.00 color rgbt <0.18, 1.00, 0.95, 0.74>]
      }
      scale 0.9
    }
    finish {
      diffuse 0.04
      specular 0.9 roughness 0.02
      reflection 0.05
      conserve_energy
    }
    normal {
      granite 0.18
      turbulence 0.8
      scale 0.18
    }
  }
}