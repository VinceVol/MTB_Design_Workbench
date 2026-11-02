//frame is a bunch of linkages together

use crate::{linkage::Linkage, shock::Shock};

pub struct Frame {
    linkages: Vec<Linkage>,
    shocks: Vec<Shock>,
}

impl Frame {
    pub fn new(linkages: Vec<Linkage>, shocks: Vec<Shock>) -> Self {
        Self { linkages, shocks }
    }
}
