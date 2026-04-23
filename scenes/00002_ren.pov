#version 3.7;

global_settings { assumed_gamma 1.0 max_trace_level 12 }

background { color rgb <0.02,0.03,0.04> }

camera {
  location <0, 0, -4.0>
  look_at  <0, 0,  0>
  angle 35
}

light_source { <3, 6, -6> color rgb <1,1,1> }
light_source { <-6, 3, -2> color rgb <0.35,0.45,0.55> }

#declare Glass_Tex =
texture{
  pigment{
    julia <0.355, 0.355> 10
    scale 0.60
    translate <0.15, -0.10, 0.05>
    turbulence 0.85
    color_map{
      [0.00 color rgbt <0.10,0.95,0.95,0.75>]
      [0.45 color rgbt <0.02,0.70,0.80,0.86>]
      [0.70 color rgbt <0.20,0.98,0.90,0.78>]
      [1.00 color rgbt <0.00,0.55,0.65,0.90>]
    }
  }
  finish{
    ambient 0
    diffuse 0.05
    specular 0.7 roughness 0.015
    reflection 0.08
  }
}

#declare Glass_Int =
interior{
  ior 1.45
  caustics 1.0
  fade_distance 1.4
  fade_power 2
  fade_color <0.00, 0.55, 0.60>
}

#declare Fuzzy_Normal =
normal{
  bumps 0.55
  scale 0.06
  turbulence 0.65
}

union{
  difference{
    box{ <-1.05,-1.05,-1.05>, < 1.05, 1.05, 1.05> }
    box{ <-0.92,-0.92,-0.92>, < 0.92, 0.92, 0.92> }
    texture{
      Glass_Tex
      normal{ Fuzzy_Normal }
    }
    interior{ Glass_Int }
    hollow
  }

  box{ <-1.08,-1.08,-1.08>, < 1.08, 1.08, 1.08>
    texture{
      Glass_Tex
      normal{ bumps 0.35 scale 0.04 turbulence 0.5 }
    }
    interior{ Glass_Int }
    hollow
    no_shadow
  }
}