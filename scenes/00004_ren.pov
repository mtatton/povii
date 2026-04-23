#version 3.7;

global_settings { assumed_gamma 1.0 max_trace_level 18 }

background { color rgb <0.01,0.02,0.03> }

camera {
  location <0, 1.5, -7>
  look_at  <0, 0,  0>
  angle 22
}

light_source { <6, 10, -10> color rgb <1.00,1.00,1.00> }
light_source { <-8, 5, -4>  color rgb <0.25,0.45,0.60> }
light_source { <0, 12, 2>   color rgb <0.20,0.30,0.35> }

#declare Glass_Tex =
texture{
  pigment{
    julia <0.355, 0.355> 10
    scale 0.55
    translate <0.10, -0.12, 0.05>
    turbulence 1.05
    color_map{
      [0.00 color rgbt <0.05,0.90,0.95,0.72>]
      [0.35 color rgbt <0.02,0.70,0.85,0.84>]
      [0.65 color rgbt <0.10,0.98,0.92,0.76>]
      [1.00 color rgbt <0.00,0.55,0.70,0.90>]
    }
  }
  finish{
    ambient 0
    diffuse 0.04
    specular 0.85 roughness 0.008
    reflection 0.10
  }
}

#declare Fuzzy_Normal =
normal{
  bumps 0.65
  scale 0.045
  turbulence 0.85
}

#declare Glass_Int =
interior{
  ior 1.47
  caustics 1.0
  fade_distance 1.2
  fade_power 2
  fade_color <0.00, 0.60, 0.70>
}

union{
  difference{
    box{ <-1.05,-1.05,-1.05>, < 1.05, 1.05, 1.05> }
    box{ <-0.90,-0.90,-0.90>, < 0.90, 0.90, 0.90> }
    texture{
      Glass_Tex
      normal{ Fuzzy_Normal }
    }
    interior{ Glass_Int }
    hollow
  }

  box{ <-1.085,-1.085,-1.085>, < 1.085, 1.085, 1.085>
    texture{
      Glass_Tex
      normal{ bumps 0.45 scale 0.035 turbulence 0.75 }
    }
    interior{ Glass_Int }
    hollow
    no_shadow
  }

  box{ <-0.89,-0.89,-0.89>, < 0.89, 0.89, 0.89>
    texture{
      pigment{ color rgbt <0.0,0.0,0.0,1> }
      finish{ emission rgb <0.01,0.08,0.09> }
    }
    hollow
    no_shadow
  }

  // Make the box smaller so it is fully inside the camera view
  scale 0.78
  rotate <0, 22, 0>
  translate <0, 0, 0>
}