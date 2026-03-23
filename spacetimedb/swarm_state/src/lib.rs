use spacetimedb::{table, reducer, ReducerContext, Table};

#[table(public, accessor = agent)]
pub struct Agent {
    #[primary_key]
    pub identity: String,
    pub name: String,
    pub status: String,
}

#[table(public, accessor = task)]
pub struct Task {
    #[primary_key]
    pub task_id: u64,
    pub description: String,
    pub status: String,
    pub depends_on: Vec<u64>,
}

#[table(public, accessor = event)]
pub struct Event {
    #[primary_key]
    pub event_id: u64,
    pub sender: String,
    pub payload: String,
    pub timestamp: u64,
}

#[reducer]
pub fn insert_event(_ctx: &ReducerContext, event: Event) {
    _ctx.db.event().insert(event);
}
