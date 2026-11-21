import json


class AgentMemory:
    def __init__(self, db):
        self.db = db

    def remember(self, role, tick, day, subject, facts, decision, reason):
        self.db.execute("INSERT OR REPLACE INTO agent_memory VALUES (?,?,?,?,?,?,?)",
                        (role, tick, day, subject, json.dumps(facts), decision, reason))

    def recall(self, role=None, limit=20):
        columns = "role,tick,day,subject,facts,decision,reason"
        if role is None:
            rows = self.db.execute(f"SELECT {columns} FROM agent_memory ORDER BY tick DESC,role LIMIT ?", (limit,))
        else:
            rows = self.db.execute(f"SELECT {columns} FROM agent_memory WHERE role=? ORDER BY tick DESC LIMIT ?", (role, limit))
        return [dict(role=role, tick=tick, day=day, subject=subject, facts=json.loads(facts), decision=decision, reason=reason)
                for role, tick, day, subject, facts, decision, reason in rows]
