use glam::{Mat2, Vec2};

//linkage is basically a bunch of points where some of those points can rotate
// we only really need to allow for the entire linkage to rotate around some of its pivot points
// with some simple methods
//
// As of now unsure what else this is going to need
pub struct Linkage {
    body: Vec<Vec2>,   //Any number of vertices can make up a linkage
    pivots: Vec<Vec2>, // same goes for pivots
}

impl Linkage {
    pub fn new(vertices: Vec<[f32; 2]>, pivot_points: Vec<[f32; 2]>) -> Self {
        let mut body: Vec<Vec2> = Vec::new();
        for vert in vertices {
            body.push(Vec2::from_array(vert));
        }

        let mut pivots: Vec<Vec2> = Vec::new();
        for point in pivot_points {
            pivots.push(Vec2::from_array(point));
        }

        Self { body, pivots }
    }

    //rotation in radians to work with no conversion for glam
    pub fn rotate(&mut self, pivot_point: Vec2, rad_rot: f32) {
        let rotation_m = Mat2::from_angle(rad_rot);

        for vert in self.body.iter_mut() {
            *vert = pivot_point + rotation_m * (*vert - pivot_point);
        }

        for pivot in self.pivots.iter_mut() {
            *pivot = pivot_point + rotation_m * (*pivot - pivot_point);
        }
    }
}
