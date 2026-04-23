#version 3.7;

global_settings {
  assumed_gamma 1.0
  max_trace_level 24
}

background { color rgb <0.005, 0.010, 0.012> }

camera {
  location <0, 0.55, -6.2>
  look_at  <0, 0.10, 0>
  angle 28
}

light_source { <-10, 14, -14> color rgb <1.7, 1.7, 1.7> }
light_source { < 10,  6, -6>  color rgb <0.55, 0.80, 1.05> }
light_source { <  0, 16,  8>  color rgb <0.25, 0.50, 0.75> }

#declare FuzzyCyanFractalGlass =
material {
  texture {
    pigment {
      granite
      turbulence 1.6
      octaves 8
      omega 0.55
      lambda 2.05
      color_map {
        [0.00 color rgbt <0.02, 0.36, 0.50, 0.965>]
        [0.22 color rgbt <0.04, 0.62, 0.78, 0.925>]
        [0.50 color rgbt <0.10, 0.92, 0.98, 0.850>]
        [0.78 color rgbt <0.04, 0.56, 0.76, 0.935>]
        [1.00 color rgbt <0.14, 1.00, 0.96, 0.820>]
      }
      scale 0.58
    }
    finish {
      diffuse 0.01
      ambient 0
      specular 0.95 roughness 0.010
      reflection 0.08
      conserve_energy
    }
    normal {
      average
      normal_map {
        [1 bumps   0.22 scale 0.070]
        [1 granite 0.48 scale 0.145 turbulence 1.05]
      }
    }
  }
  interior {
    ior 1.53
    caustics 1.0
    fade_distance 1.8
    fade_power 1.35
    fade_color <0.03, 0.80, 0.90>
  }
}

#declare BoxSize = 1.05;

box {
  <-BoxSize, -BoxSize, -BoxSize>, <BoxSize, BoxSize, BoxSize>
  material { FuzzyCyanFractalGlass }
  hollow
  photons { target reflection on refraction on }
  rotate <6, -18, 0>
}

sphere {
  <0,0,0>, 0.001
  pigment { color rgbt 1 }
  finish { ambient 0 diffuse 0 }
  no_shadow
}