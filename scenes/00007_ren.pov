#version 3.7;

global_settings {
  assumed_gamma 1.0
  max_trace_level 18
}

background { color rgb <0.01, 0.02, 0.025> }

camera {
  location <0, 1.5, -9>
  look_at  <0, 0, 0>
  angle 24
}

light_source { <-10, 14, -14> color rgb <1.6, 1.6, 1.6> }
light_source { < 10,  6, -6>  color rgb <0.55, 0.75, 0.95> }
light_source { <  0, 16,  8>  color rgb <0.25, 0.45, 0.65> }

#declare FuzzyCyanFractalGlass =
material {
  texture {
    pigment {
      granite
      turbulence 1.4
      octaves 7
      omega 0.55
      lambda 2.05
      color_map {
        [0.00 color rgbt <0.02, 0.42, 0.55, 0.94>]
        [0.30 color rgbt <0.05, 0.70, 0.82, 0.88>]
        [0.58 color rgbt <0.12, 0.95, 0.98, 0.80>]
        [0.82 color rgbt <0.04, 0.58, 0.78, 0.90>]
        [1.00 color rgbt <0.16, 1.00, 0.96, 0.76>]
      }
      scale 0.62
    }
    finish {
      diffuse 0.02
      specular 0.95 roughness 0.012
      reflection 0.06
      conserve_energy
    }
    normal {
      average
      normal_map {
        [1 bumps   0.26 scale 0.085]
        [1 granite 0.38 scale 0.18 turbulence 0.9]
      }
    }
  }
  interior {
    ior 1.53
    caustics 1.0
    fade_distance 2.4
    fade_power 1.2
    fade_color <0.05, 0.85, 0.90>
  }
}

#declare BoxSize = 1.65;

box {
  <-BoxSize, -BoxSize, -BoxSize>, <BoxSize, BoxSize, BoxSize>
  material { FuzzyCyanFractalGlass }
  hollow
  photons { target reflection on refraction on }
}

sphere {
  <0,0,0>, 0.001
  pigment { color rgbt 1 }
  finish { ambient 0 diffuse 0 }
  no_shadow
}