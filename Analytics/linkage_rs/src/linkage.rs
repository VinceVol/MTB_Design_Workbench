use glam::Vec2;

//linkage is basically a bunch of points where some of those points can rotate
// we only really need to allow for the entire linkage to rotate around some of its pivot points
// with some simple methods
//
// As of now unsure what else this is going to need
struct Linkage {
    body: Vec<Vec2>,   //Any number of vertices can make up a linkage
    pivots: Vec<Vec2>, // same goes for pivots
}

impl Linkage {
    fn new(vertices: Vec<[f32; 2]>, pivot_points: Vec<[f32; 2]>) -> Self {
        let mut body: Vec<Vec2> = Vec::new();
        for vert in vertices {
            body.push(Vec2::from_array(vert));
        }

        todo!();
    }
}
