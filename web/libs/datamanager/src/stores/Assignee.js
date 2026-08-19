import { types } from "mobx-state-tree";
import { User } from "./Users";
import { StringOrNumberID } from "./types";

const USER_CHIP_FIELDS = ["annotators", "reviewers", "updated_by", "comment_authors"];

function isNumericUserId(value) {
  return typeof value === "number" && Number.isFinite(value);
}

/**
 * Return the User id that Assignee.preProcessSnapshot will store as a
 * `types.reference(User)`. Full nested user objects are ignored so we never
 * insert a stub that collides with an identifier already owned by that object.
 */
export function referencedUserIdFromAssigneeSnapshot(sn) {
  if (isNumericUserId(sn)) return sn;
  if (!sn || typeof sn !== "object") return null;

  const { user_id, user: nestedUser, annotated, review, reviewed, ...user } = sn;
  const id = user_id ?? sn.id;

  if (nestedUser && typeof nestedUser === "object") return null;
  if (isNumericUserId(nestedUser)) return nestedUser;

  const hasUserProperties = Object.keys(user).length > 0;

  if (hasUserProperties) return null;
  return isNumericUserId(id) ? id : null;
}

export function collectReferencedUserIds(record) {
  if (!record || typeof record !== "object") return [];
  const ids = [];

  for (const field of USER_CHIP_FIELDS) {
    const items = record[field];
    if (!Array.isArray(items)) continue;
    for (const item of items) {
      const id = referencedUserIdFromAssigneeSnapshot(item);
      if (id != null) ids.push(id);
    }
  }

  return ids;
}

// Create a union type that can handle both user references and direct user objects
const UserOrReference = types.union({
  dispatcher: (snapshot) => {
    // If it's a full user object (has firstName, email, etc.), use User model
    if (snapshot && typeof snapshot === "object" && (snapshot.firstName || snapshot.email || snapshot.username)) {
      return User;
    }
    // Otherwise, it's a reference to a user ID
    return types.reference(User);
  },
  cases: {
    [User.name]: User,
    reference: types.reference(User),
  },
});

export const Assignee = types
  .model("Assignee", {
    id: StringOrNumberID,
    user: types.late(() => UserOrReference),
    review: types.maybeNull(types.enumeration(["accepted", "rejected", "fixed"])),
    reviewed: types.maybeNull(types.boolean),
    annotated: types.maybeNull(types.boolean),
  })
  .views((self) => ({
    get firstName() {
      return self.user.firstName;
    },
    get lastName() {
      return self.user.lastName;
    },
    get username() {
      return self.user.username;
    },
    get email() {
      return self.user.email;
    },
    get lastActivity() {
      return self.user.lastActivity;
    },
    get avatar() {
      return self.user.avatar;
    },
    get initials() {
      return self.user.initials;
    },
    get fullName() {
      return self.user.fullName;
    },
  }))
  .preProcessSnapshot((sn) => {
    let result = sn;

    if (typeof sn === "number") {
      result = {
        id: sn,
        user: sn,
        annotated: true,
        review: null,
        reviewed: false,
      };
    } else {
      const { user_id, user: nestedUser, annotated, review, reviewed, ...user } = sn;
      const id = user_id ?? sn.id;

      const hasUserProperties = Object.keys(user).length > 0;

      let resolvedUser = id;
      if (nestedUser && typeof nestedUser === "object") {
        resolvedUser = nestedUser;
      } else if (hasUserProperties) {
        resolvedUser = { id, ...user };
      }

      result = {
        id,
        user: resolvedUser,
        annotated,
        review,
        reviewed,
      };
    }

    return result;
  });
