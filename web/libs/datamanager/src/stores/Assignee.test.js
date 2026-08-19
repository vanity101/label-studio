import { types } from "mobx-state-tree";
import { Assignee, collectReferencedUserIds, referencedUserIdFromAssigneeSnapshot } from "./Assignee";
import { User } from "./Users";

describe("Assignee preProcessSnapshot (FIT-1658)", () => {
  let ff;

  beforeEach(() => {
    ff = mockFF();
    ff.setup();
  });

  afterEach(() => {
    ff.reset();
  });

  it("embeds flat profile fields from API payload", () => {
    const row = Assignee.create({
      user_id: 42,
      id: 42,
      first_name: "Sam",
      last_name: "",
      email: "sam@example.com",
      username: "sam",
      last_activity: "",
      avatar: null,
      initials: "S",
      annotated: true,
      review: null,
      reviewed: false,
    });

    expect(row.email).toBe("sam@example.com");
    expect(row.firstName).toBe("Sam");
  });

  it("embeds nested user object when API provides user", () => {
    const row = Assignee.create({
      id: 9,
      user: {
        id: 9,
        first_name: "Rae",
        email: "rae@example.com",
        last_name: "Lee",
        username: "rae",
        lastActivity: "",
        avatar: null,
        initials: "RL",
      },
      annotated: true,
      review: null,
      reviewed: false,
    });

    expect(row.email).toBe("rae@example.com");
  });
});

describe("Data Manager User reference stubs", () => {
  const TaskRow = types.model("TaskRow", {
    id: types.identifierNumber,
    annotators: types.optional(types.array(Assignee), []),
  });

  const Root = types
    .model("Root", {
      users: types.optional(types.array(User), []),
      list: types.optional(types.array(TaskRow), []),
    })
    .actions((self) => ({
      ensureUserStubs(ids) {
        const have = new Set(self.users.map((user) => Number(user.id)));
        for (const raw of ids) {
          const id = Number(raw);
          if (!Number.isFinite(id) || have.has(id)) continue;
          self.users.push({ id });
          have.add(id);
        }
      },
      setList(list) {
        self.ensureUserStubs(list.flatMap((item) => collectReferencedUserIds(item)));
        self.list = list;
      },
    }));

  it("treats bare numeric annotators as User references", () => {
    expect(referencedUserIdFromAssigneeSnapshot(1)).toBe(1);
    expect(referencedUserIdFromAssigneeSnapshot({ user_id: 7 })).toBe(7);
    expect(referencedUserIdFromAssigneeSnapshot({ user_id: 42, email: "sam@example.com" })).toBeNull();
    expect(collectReferencedUserIds({ annotators: [1], reviewers: [{ user_id: 2 }] })).toEqual([1, 2]);
  });

  it("does not throw when annotators are [1] and users is empty", () => {
    const root = Root.create({ users: [] });

    expect(() => root.setList([{ id: 2, annotators: [1] }])).not.toThrow();
    expect(root.users.map((user) => user.id)).toEqual([1]);
    expect(root.list[0].annotators[0].user.id).toBe(1);
  });
});
