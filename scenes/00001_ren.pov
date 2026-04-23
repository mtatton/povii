// Medieval cityscape with added details, softer warm light, and lower camera (POV-Ray 3.7)

#version 3.7;

global_settings {
    assumed_gamma 1.8 max_trace_level 19
    radiosity {
        pretrace_start 0.08
        pretrace_end   0.01
        count 200
        nearest_count 15
        error_bound 0.5
        recursion_limit 2
        low_error_factor 0.5
        gray_threshold 0.0
    }
}

// Soft cloudy sky with smooth gradient (web-safe blues and white)
sky_sphere {
    pigment {
        bozo
        color_map {
            [0.00 color rgb <0.4, 0.6, 0.8>]
            [0.55 color rgb <0.6, 0.8, 1.0>]
            [0.80 color rgb <1.0, 1.0, 1.0>]
            [1.00 color rgb <1.0, 1.0, 1.0>]
        }
        turbulence 0.8
        omega 0.55
        lambda 2.0
        octaves 5
        scale 0.6
    }
}

// Fallback background color (web-safe)
background { color rgb <0.6, 0.8, 1.0> }

// Camera: moved a bit lower and slightly closer for a stronger street-level feel
camera {
    location  <-42, 25, -75>
    look_at   <0, 2, 0>
    right     x*image_width/image_height
    angle     45
}

// Warm conical area spotlights for soft shadows and lifted mids
light_source {
    <-120, 110, -180>
    color rgb <1.0, 0.85, 0.7> * 0.3
    spotlight
    point_at <0, 8, 0>
    radius 32
    falloff 64
    tightness 6
    area_light <14,0,0>, <0,14,0>, 6, 6
    adaptive 1
    jitter
    circular
    orient
}

light_source {
    <120, 64, -80>
    color rgb <1.0, 0.85, 0.7> * 0.3
    spotlight
    point_at <0, 8, 0>
    radius 36
    falloff 72
    tightness 5
    area_light <12,0,0>, <0,12,0>, 5, 5
    adaptive 1
    jitter
    circular
    orient
}

// Gentle sky-fill conical area light to brighten overall tones (keeps shadows soft)
light_source {
    <0, 140, 40>
    color rgb <1.0, 0.9, 0.8>*0.35
    spotlight
    point_at <0, 6, 0>
    radius 65
    falloff 88
    tightness 4
    area_light <18,0,0>, <0,18,0>, 5, 5
    adaptive 1
    jitter
    circular
    orient
}

// Subtle atmospheric haze for depth (fast)
fog {
    distance 450
    color rgb <1.0, 1.0, 1.0>*0.01
}

// Finishes and base web-safe colors
#declare Finish_Matte = finish { diffuse 0.92 specular 0.06 roughness 0.02 };
#declare Finish_Soft  = finish { diffuse 0.88 specular 0.10 roughness 0.02 };
#declare Col_Stone    = <0.6, 0.6, 0.6>;
#declare Col_RoofRed  = <0.8, 0.2, 0.2>;
#declare Col_WoodA    = <0.4, 0.2, 0.0>;
#declare Col_Plaster  = <1.0, 1.0, 0.8>;
#declare Col_Slate    = <0.4, 0.4, 0.4>;
#declare Col_Keep     = <0.8, 0.8, 0.8>;
#declare Col_GrassA   = <0.8, 1.0, 0.8>;
#declare Col_GrassB   = <0.6, 0.8, 0.6>;
#declare Col_WaterA   = <0.0, 0.4, 0.6>;
#declare Col_WaterB   = <0.0, 0.6, 0.8>;
#declare Col_Mortar   = <0.8, 0.8, 0.8>;
#declare Col_ShadowWin= <0.2, 0.2, 0.2>;
#declare Col_BannerR  = <0.8, 0.2, 0.2>;
#declare Col_BannerB  = <0.2, 0.6, 0.8>;

// Lightweight procedural textures (fast, smooth, web-safe palette)
#macro TexStoneAshlar(BaseCol, MortarCol)
    texture {
        pigment {
            brick color rgb BaseCol, color rgb MortarCol
            brick_size <1.8, 0.6, 1.2>
            mortar 0.06
            scale 2
        }
        normal { bumps 0.22 scale 0.5 }
        finish { Finish_Matte }
    }
#end

#macro TexStoneSoft(BaseCol)
    texture {
        pigment {
            bozo
            color_map {
                [0.0 color rgb (BaseCol*0.94)]
                [1.0 color rgb (BaseCol*1.04)]
            }
            turbulence 0.25
            scale 3
        }
        normal { granite 0.18 scale 0.8 }
        finish { Finish_Matte }
    }
#end

#macro TexSlateRoof(BaseCol)
    texture {
        pigment {
            brick color rgb (BaseCol*0.95), color rgb (BaseCol*1.05)
            brick_size <0.6, 0.2, 0.6>
            mortar 0.02
            scale 0.8
        }
        normal { wrinkles 0.15 scale 0.25 }
        finish { diffuse 0.86 specular 0.12 roughness 0.03 }
    }
#end

#macro TexPlasterStucco(BaseCol)
    texture {
        pigment {
            bozo
            color_map {
                [0.0 color rgb (BaseCol*0.96)]
                [1.0 color rgb (BaseCol*1.00)]
            }
            turbulence 0.2
            scale 4
        }
        normal { bumps 0.12 scale 0.35 }
        finish { Finish_Soft }
    }
#end

#macro TexWoodPlank()
    texture {
        pigment {
            gradient x
            color_map {
                [0.0 color rgb <0.4, 0.2, 0.0>]
                [0.5 color rgb <0.6, 0.4, 0.2>]
                [1.0 color rgb <0.4, 0.2, 0.0>]
            }
            scale 0.35
        }
        normal { wood 0.25 scale 0.6 }
        finish { Finish_Soft }
    }
#end

#macro TexGrass()
    texture {
        pigment {
            bozo
            color_map {
                [0.0 color rgb Col_GrassA]
                [1.0 color rgb Col_GrassB]
            }
            turbulence 0.2
            scale 20
        }
        normal { bumps 0.30 scale 8 }
        finish { Finish_Matte }
    }
#end

#macro TexWater()
    texture {
        pigment {
            bozo
            color_map {
                [0.0 color rgb Col_WaterA]
                [1.0 color rgb Col_WaterB]
            }
            turbulence 0.15
            scale 10
        }
        normal { ripples 0.55 frequency 3 scale 1.8 }
        finish { diffuse 0.7 specular 0.2 roughness 0.01 reflection 0.05 }
    }
#end

#macro TexCobbles()
    texture {
        pigment {
            crackle
            color_map {
                [0.0 color rgb <0.6,0.6,0.6>]
                [1.0 color rgb <0.8,0.8,0.8>]
            }
            form <1,0,0>
            metric 1.2
            scale 0.7
        }
        normal { bumps 0.25 scale 0.3 }
        finish { Finish_Matte }
    }
#end

// Helpful transforms
#declare UpEps = <0, 0.001, 0>;

// Far ground plane (smooth warm gradient + subtle bumps)
plane {
    y, 0
    texture {
        pigment {
            gradient z
            color_map {
                [0.0 color rgb <1.0, 1.0, 0.8>]
                [1.0 color rgb <0.8, 1.0, 0.8>]
            }
            scale 200
        }
        normal { bumps 0.35 scale 60 }
        finish { Finish_Matte }
    }
}

// Near-city raised ground disk for moat/streets
cylinder {
    <0, 0.0, 0>, <0, 0.10, 0>, 36.5
    TexGrass()
    translate UpEps
}

// Shallow circular moat (ring)
difference {
    cylinder { <0, 0.001, 0>, <0, 0.025, 0>, 48 }   // outer
    cylinder { <0, -0.01, 0>, <0, 0.05, 0>, 38 }   // inner hole
    TexWater()
}

// Small timber bridge across the moat, aligned with gate (outer ring)
#declare BridgeZ1 = -38.0;
#declare BridgeZ2 = -50.0;
union {
    // deck planks
    #declare p = -2.0;
    #while (p <= 2.0)
        box { <p-0.18, 0.02, BridgeZ1>, <p+0.18, 0.10, BridgeZ2> TexWoodPlank() }
        #declare p = p + 0.4;
    #end
    // simple side rails
    box { <-2.2, 0.10, BridgeZ1>, <-1.8, 0.34, BridgeZ2> TexWoodPlank() }
    box { < 1.8, 0.10, BridgeZ1>, < 2.2, 0.34, BridgeZ2> TexWoodPlank() }
}
// Causeway from inner bank to the city gate
box { <-1.0, 0.012, -26.0>, <1.0, 0.040, -38.0> TexCobbles() }

// City wall: hollow ring of stone with a simple gate opening facing camera
difference {
    cylinder { <0, 0, 0>, <0, 8, 0>, 30 }   // Outer wall
    cylinder { <0, 0, 0>, <0, 8, 0>, 26 }   // Inner void
    box { <-3, 0, -40>, <3, 5.5, -25.5> }  // Gate cutout
    TexStoneAshlar(Col_Stone, Col_Mortar)
}

// Wall-walk deck just inside the crenellations (precisely below y=8 top)
difference {
    cylinder { <0, 7.70, 0>, <0, 7.90, 0>, 29.2 }
    cylinder { <0, 7.60, 0>, <0, 8.20, 0>, 26.3 }
    TexWoodPlank()
}

// Crenellations (merlons) on the wall top, skipping gate sector
union {
    #declare k = 0;
    #for (k, 0, 29)
        #declare a = k*12; // 30 around
        // Skip near 270 degrees (toward the gate at -Z)
        #if (abs(a-270) > 16)
            box { <-0.6, 8.0, 28.2>, <0.6, 9.2, 30.0> rotate <0, a, 0> TexStoneAshlar(Col_Stone, Col_Mortar) }
        #end
    #end
}

// Gatehouse beam and portcullis within the opening (aligned to the cut)
union {
    // Lintel beam
    box { <-3.1, 5.3, -26.0>, <3.1, 5.8, -25.4> TexStoneSoft(<0.6,0.6,0.6>) }
    // Portcullis bars just inside gate
    #declare bx = -2.4;
    #while (bx <= 2.4)
        box { <bx-0.06, 0.2, -26.1>, <bx+0.06, 5.2, -25.7> TexWoodPlank() }
        #declare bx = bx + 0.6;
    #end
    // Bottom bar
    box { <-2.5, 0.14, -26.1>, <2.5, 0.28, -25.7> TexWoodPlank() }
}

// Two small square gate towers outside the opening with connecting bridge
#macro GateSquareTower(Pos)
    union {
        difference {
            box { <-1.6, 0, -1.6>, <1.6, 7.2, 1.6> }
            // Arrow slits
            box { <-0.25, 2.0, -1.8>, <0.25, 5.2, -1.2> }
            box { <-1.8, 2.0, -0.25>, <-1.2, 5.2, 0.25> }
            box { < 1.2, 2.0, -0.25>, < 1.8, 5.2, 0.25> }
            box { <-0.18, 3.4,  1.2>, <0.18, 4.6, 1.8> }
            TexStoneAshlar(Col_Stone, Col_Mortar)
        }
        // Conical cap
        cone { <0, 9.2, 0>, 0, <0, 7.2, 0>, 2.0 TexSlateRoof(Col_Slate) }
        translate Pos
    }
#end

GateSquareTower(<-4.8, 0, -29.0>)
GateSquareTower(< 4.8, 0, -29.0>)

// Over-gate stone bridge connecting the square towers
box { <-3.4, 5.6, -27.8>, <3.4, 6.2, -26.0> TexStoneAshlar(Col_Stone, Col_Mortar) }

// Round tower macro
#macro RoundTower(Pos, Radius, Height, RoofH, WallCol, RoofCol)
    union {
        cylinder { <0, 0, 0>, <0, Height, 0>, Radius  TexStoneAshlar(WallCol, Col_Mortar) }
        cone     { <0, Height + RoofH, 0>, 0, <0, Height, 0>, Radius TexSlateRoof(RoofCol) }
        translate Pos
    }
#end

RoundTower(< 28, 0,   0>, 3.0, 12.0, 4.0, Col_Stone, Col_Slate)
RoundTower(<-28, 0,   0>, 3.0, 12.0, 4.0, Col_Stone, Col_Slate)
RoundTower(<  0, 0,  28>, 3.0, 12.0, 4.0, Col_Stone, Col_Slate)
RoundTower(<  0, 0, -28>, 3.0, 12.0, 4.0, Col_Stone, Col_Slate)

// Central keep: tall round tower with higher conical roof
union {
    cylinder { <0, 0, 0>, <0, 14, 0>, 6  TexStoneSoft(Col_Keep) }
    cone     { <0, 20, 0>, 0, <0, 14, 0>, 6 TexSlateRoof(Col_Slate) }
}

// Gabled house macro (precise alignment; roof sits flush on body)
#macro GableHouse(Pos, Yaw, W, D, H, RH, WallCol, RoofCol)
    union {
        // House body
        box { <-W/2, 0, -D/2>, < W/2, H, D/2>  TexPlasterStucco(WallCol) }

        // Gabled roof: triangular prism extruded along depth (Z)
        prism {
            linear_spline
            -D/2, D/2,
            4,
            <-W/2, 0>, <0, RH>, < W/2, 0>, <-W/2, 0>
            rotate -90*x
            translate <0, H, 0>
            TexSlateRoof(RoofCol)
        }

        // Half-timber beams (front/back and sides)
        #declare th = min(W,D)*0.06;
        // Front horizontal
        box { <-W/2, H*0.5 - th/2, -D/2 - 0.015>, < W/2, H*0.5 + th/2, -D/2 + 0.015> TexWoodPlank() }
        // Front verticals
        box { <-W*0.35 - th/2, 0, -D/2 - 0.015>, <-W*0.35 + th/2, H, -D/2 + 0.015> TexWoodPlank() }
        box { <-th/2,          0, -D/2 - 0.015>, < th/2,          H, -D/2 + 0.015> TexWoodPlank() }
        box { < W*0.35 - th/2, 0, -D/2 - 0.015>, < W*0.35 + th/2, H, -D/2 + 0.015> TexWoodPlank() }
        // Back
        box { <-W/2, H*0.5 - th/2,  D/2 - 0.015>, < W/2, H*0.5 + th/2,  D/2 + 0.015> TexWoodPlank() }
        // Sides vertical posts
        box { <-W/2 - 0.015, 0, -D/2>, <-W/2 + 0.015, H,  D/2> TexWoodPlank() }
        box { < W/2 - 0.015, 0, -D/2>, < W/2 + 0.015, H,  D/2> TexWoodPlank() }

        // Wooden door centered on front face
        box {
            <-W*0.12, 0, -D/2 - 0.02>, < W*0.12, H*0.45, -D/2 + 0.02>
            TexWoodPlank()
        }
        // Small dark window above door
        box {
            <-W*0.08, H*0.60, -D/2 - 0.02>, <W*0.08, H*0.78, -D/2 + 0.02>
            texture { pigment { color rgb Col_ShadowWin } finish { diffuse 0.2 specular 0 } }
        }
        // Tiny chimney on one roof edge
        box { < W*0.30-0.10, H+RH*0.55, -D*0.15-0.10>, < W*0.30+0.10, H+RH*0.95, -D*0.15+0.10> TexStoneSoft(<0.7,0.7,0.7>) }

        rotate <0, Yaw, 0>
        translate Pos
    }
#end

// Market stall macro
#macro MarketStall(Pos, Yaw, W, D, H, ClothCol)
    union {
        // poles
        #declare px = -W/2;
        #while (px <= W/2)
            box { <px-0.05, 0, -D/2+0.05>, <px+0.05, H, -D/2-0.05> TexWoodPlank() }
            box { <px-0.05, 0,  D/2-0.05>, <px+0.05, H,  D/2+0.05> TexWoodPlank() }
            #declare px = px + W;
        #end
        // roof cloth
        prism {
            linear_spline
            -D/2, D/2,
            4,
            <-W/2, 0>, <0, H*0.45>, <W/2, 0>, <-W/2, 0>
            rotate -90*x
            translate <0, H, 0>
            texture {
                pigment {
                    gradient x
                    color_map {
                        [0.0 color rgb (ClothCol*0.9)]
                        [1.0 color rgb (ClothCol*1.1)]
                    }
                    scale W
                }
                finish { Finish_Matte }
            }
        }
        rotate <0, Yaw, 0>
        translate Pos
    }
#end

// Simple flag/pennant macro for towers
#macro Flag(Pos, Yaw, PoleH, FlagW, ColA, ColB)
    union {
        // pole
        cylinder { <0, 0, 0>, <0, PoleH, 0>, 0.06 TexWoodPlank() }
        // small finial
        sphere { <0, PoleH, 0>, 0.08 texture { pigment { color rgb <0.6,0.4,0.2> } finish { Finish_Soft } } }
        // pennant
        prism {
            linear_spline
            0.0, 0.02,
            5,
            <0, 0.6>, <FlagW*0.6, 0.3>, <FlagW, 0.5>, <FlagW*0.6, 0.1>, <0, 0.6>
            texture {
                pigment {
                    gradient x
                    color_map { [0 color rgb ColA] [1 color rgb ColB] }
                    scale FlagW
                }
                finish { Finish_Matte }
            }
            rotate <0, 90, 0>
            translate <0, PoleH-0.4, 0>
        }
        rotate <0, Yaw, 0>
        translate Pos
    }
#end

// Small props: barrels, crates, and a hand cart
#macro Barrel(Pos, H, R)
    union {
        cylinder { <0, 0, 0>, <0, H, 0>, R texture { pigment { color rgb <0.6,0.4,0.2> } finish { Finish_Soft } } }
        cylinder { <0, H*0.08, 0>, <0, H*0.12, 0>, R*1.02 texture { pigment { color rgb <0.4,0.4,0.4> } finish { Finish_Matte } } }
        cylinder { <0, H*0.88, 0>, <0, H*0.92, 0>, R*1.02 texture { pigment { color rgb <0.4,0.4,0.4> } finish { Finish_Matte } } }
        translate Pos
    }
#end

#macro Crate(Pos, S)
    union {
        box { <-S/2, 0, -S/2>, <S/2, S, S/2> TexWoodPlank() }
        // iron straps
        box { <-S/2-0.005, S*0.45, -S/2-0.005>, <-S/2+0.02, S*0.55, S/2+0.005> texture { pigment { color rgb <0.5,0.5,0.5> } finish { Finish_Matte } } }
        box { < S/2-0.02, S*0.45, -S/2-0.005>, < S/2+0.005, S*0.55, S/2+0.005> texture { pigment { color rgb <0.5,0.5,0.5> } finish { Finish_Matte } } }
        translate Pos
    }
#end

#macro Cart(Pos, Yaw)
    union {
        // bed
        box { <-1.6, 0.4, -0.8>, <1.6, 0.7, 0.8> TexWoodPlank() }
        // side rails
        box { <-1.6, 0.7, -0.8>, <1.6, 0.85, -0.68> TexWoodPlank() }
        box { <-1.6, 0.7,  0.68>, <1.6, 0.85,  0.8> TexWoodPlank() }
        // shafts
        box { <1.6, 0.5, -0.12>, <2.8, 0.62, 0.12> TexWoodPlank() }
        // wheels (simple tori)
        torus { 0.55, 0.08 texture { pigment { color rgb <0.5,0.3,0.1> } finish { Finish_Soft } } rotate <0,0,90> translate <-1.5, 0.55,  0.9> }
        torus { 0.55, 0.08 texture { pigment { color rgb <0.5,0.3,0.1> } finish { Finish_Soft } } rotate <0,0,90> translate <-1.5, 0.55, -0.9> }
        rotate <0, Yaw, 0>
        translate Pos
    }
#end

// Inner ring of houses facing outward (visible from above)
#declare i = 0;
#for (i, 0, 7)
    #declare ang = i*45;
    #declare rad = 16.0;
    #declare hx  = rad*cos(radians(ang));
    #declare hz  = rad*sin(radians(ang));
    GableHouse(<hx, 0, hz>, 180 - ang, 5.0, 4.0, 3.5, 1.5, Col_Plaster, Col_RoofRed)
#end

// Second ring of smaller cottages, slightly staggered
#declare j = 0;
#for (j, 0, 9)
    #declare ang2 = j*36 + 18;
    #declare rad2 = 11.0;
    #declare sx   = rad2*cos(radians(ang2));
    #declare sz   = rad2*sin(radians(ang2));
    GableHouse(<sx, 0, sz>, 180 - ang2, 3.8, 3.2, 3.0, 1.2, Col_Plaster, <0.6, 0.2, 0.0>)
#end

// A few houses near the gate line to suggest a street
GableHouse(<20, 0, -12>,  90, 4.8, 3.6, 3.4, 1.4, Col_Plaster, Col_RoofRed)
GableHouse(<22, 0,  -8>, 110, 4.2, 3.4, 3.2, 1.3, Col_Plaster, <0.6, 0.2, 0.0>)
GableHouse(<18, 0, -16>,  70, 4.6, 3.6, 3.3, 1.3, Col_Plaster, Col_RoofRed)

// Market stalls near the ring road
MarketStall(<-8, 0, -6>,  45, 3.0, 2.0, 1.6, <0.8,0.2,0.2>)
MarketStall(< 8, 0,  6>, -30, 3.2, 2.2, 1.6, <0.2,0.6,0.8>)

// Props around the market
Barrel(<-9.0, 0.012, -6.8>, 0.9, 0.35)
Crate (<-7.0, 0.012, -5.0>, 0.7)
Barrel(< 8.6, 0.012,  5.2>, 0.9, 0.35)
Crate (< 9.2, 0.012,  6.9>, 0.7)

// Low inner court platform (precise thin disk)
cylinder {
    <0, 0.001, 0>, <0, 0.005, 0>, 10
    texture {
        pigment { gradient x color_map { [0 color rgb <0.8, 1.0, 0.8>] [1 color rgb <0.6, 0.8, 0.6>] } scale 10 }
        finish  { Finish_Matte }
    }
}

// Streets: central road from gate to keep, ring road, and two radials
box { <-1.2, 0.012, -26.0>, <1.2, 0.040, 0.2> TexCobbles() }
difference {
    cylinder { <0, 0.012, 0>, <0, 0.040, 0>, 16.5 }
    cylinder { <0, -0.01, 0>, <0, 0.05, 0>, 15.3 }
    TexCobbles()
}
// Diagonal radial streets
box { <-0.8, 0.012, 0>, <0.8, 0.040, 15> rotate <0, 45, 0> TexCobbles() }
box { <-0.8, 0.012, 0>, <0.8, 0.040, 15> rotate <0,-45, 0> TexCobbles() }

// A simple stone well on the court
difference {
    cylinder { <4, 0.012, 3>, <4, 1.0, 3>, 1.2 }
    cylinder { <4, 0.1,   3>, <4, 0.9, 3>, 0.9 }
    TexStoneAshlar(<0.6,0.6,0.6>, Col_Mortar)
}
cylinder { <4, 0.30, 3>, <4, 0.32, 3>, 0.85 TexWater() }

// Hand cart near the gate and a couple of barrels
Cart(<-6.5, 0, -20.0>, 15)
Barrel(<-7.6, 0.012, -19.0>, 0.9, 0.35)
Barrel(<-6.0, 0.012, -21.2>, 0.9, 0.35)

// Flags atop the four round towers for a medieval touch
Flag(< 28, 12.0,   0>,   90, 2.2, 1.8, Col_BannerR, <1.0,1.0,0.8>)
Flag(<-28, 12.0,   0>,  -90, 2.2, 1.8, Col_BannerB, <1.0,1.0,0.8>)
Flag(<  0, 12.0,  28>,  180, 2.2, 1.8, Col_BannerR, Col_BannerB)
Flag(<  0, 12.0, -28>,    0, 2.2, 1.8, Col_BannerB, Col_BannerR)
