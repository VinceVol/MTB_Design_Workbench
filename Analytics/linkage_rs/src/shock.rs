//Using this to model the shock (obviously) essentially the a shock is just a linkage with two pivots and a adjustable distance
// between those pivots

use crate::linkage::Linkage;

//TODO Trying to determine whether the shock struct should keep track of progressivity information TODO
pub struct Shock {
    linkage: Linkage,
    stroke: u64, //mm
}

impl Shock {
    pub fn new(rear_pivot: [f32; 2], front_pivot: [f32; 2], stroke: u64) -> Self {
        Self {
            linkage: Linkage::new(vec![front_pivot, rear_pivot], vec![front_pivot, rear_pivot]),
            stroke,
        }
    }
    pub fn compress(&mut self, amount: u64) {
        //pretty idiodic function for now but this will likely need to evolve into
        // something that references a force/compression curve foor specific shocks
        self.stroke -= amount;
    }
}
