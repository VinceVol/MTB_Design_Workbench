//Using this to model the shock (obviously) essentially the a shock is just a linkage with two pivots and a adjustable distance
// between those pivots

use crate::linkage::Linkage;

//TODO Trying to determine whether the shock struct should keep track of progressivity information TODO
struct Shock {
    linkage: Linkage,
    stroke: u64, //mm
}
