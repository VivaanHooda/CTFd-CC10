// The site's own confirm/alert dialogs, in place of the browser's "localhost says..." boxes.
// Built on <dialog>.showModal(), so it sits in the top layer above Bootstrap modals.

let queue = Promise.resolve();

function build({ title, message, confirmLabel, cancelLabel }) {
  const dialog = document.createElement("dialog");
  dialog.className = "voyage-dialog";
  dialog.setAttribute("aria-labelledby", "voyage-dialog-title");

  const heading = document.createElement("h2");
  heading.id = "voyage-dialog-title";
  heading.className = "notice-title";
  heading.textContent = title;

  const body = document.createElement("div");
  body.className = "notice-text";
  // messages are plain text; keep their line breaks
  String(message)
    .split("\n")
    .filter(line => line.trim() !== "")
    .forEach(line => {
      const p = document.createElement("p");
      p.textContent = line;
      body.appendChild(p);
    });

  const actions = document.createElement("div");
  actions.className = "voyage-dialog-actions";

  let cancel = null;
  if (cancelLabel) {
    cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "btn-3d btn-3d--muted voyage-dialog-cancel";
    cancel.textContent = cancelLabel;
    actions.appendChild(cancel);
  }

  const confirm = document.createElement("button");
  confirm.type = "button";
  confirm.className = "btn-3d voyage-dialog-confirm";
  confirm.textContent = confirmLabel;
  actions.appendChild(confirm);

  dialog.append(heading, body, actions);
  return { dialog, confirm, cancel };
}

function open(options) {
  const { dialog, confirm, cancel } = build(options);
  // Inside an open Bootstrap modal its focus trap would pull focus back out of the dialog,
  // so the dialog lives inside that modal (it still renders in the top layer).
  const host = document.querySelector(".modal.show") || document.body;
  host.appendChild(dialog);

  return new Promise(resolve => {
    let answer = false;
    const finish = value => {
      answer = value;
      dialog.close();
    };
    confirm.addEventListener("click", () => finish(true));
    if (cancel) cancel.addEventListener("click", () => finish(false));
    // Escape cancels a confirm and dismisses an alert
    dialog.addEventListener("cancel", event => {
      event.preventDefault();
      finish(!cancel);
    });
    // clicking the dimmed backdrop does the same as Escape
    dialog.addEventListener("click", event => {
      if (event.target === dialog) finish(!cancel);
    });
    dialog.addEventListener(
      "close",
      () => {
        dialog.remove();
        resolve(answer);
      },
      { once: true },
    );
    dialog.showModal();
    (cancel || confirm).focus();
  });
}

// one dialog at a time, in the order they were asked for
function enqueue(options) {
  const next = queue.then(() => open(options));
  queue = next.catch(() => {});
  return next;
}

export function voyageConfirm(
  message,
  { title = "Are you sure?", confirmLabel = "Confirm", cancelLabel = "Cancel" } = {},
) {
  return enqueue({ title, message, confirmLabel, cancelLabel });
}

export function voyageAlert(
  message,
  { title = "Notice", confirmLabel = "Got it" } = {},
) {
  return enqueue({ title, message, confirmLabel, cancelLabel: null });
}

// Route ctfd-js's built-in confirm()/alert() hooks through the site's dialogs
export default CTFd => {
  const challenge = CTFd._functions.challenge;

  challenge.displayHint = hint => voyageAlert(hint.content, { title: "Hint" });

  challenge.displayUnlock = () =>
    voyageConfirm("Unlocking this hint may cost you points.", {
      title: "Unlock this hint?",
      confirmLabel: "Unlock",
    });
  challenge.displayHintUnlock = challenge.displayUnlock;

  challenge.displaySolutionUnlock = () =>
    voyageConfirm("Once you view the solution you can't take it back.", {
      title: "Unlock the solution?",
      confirmLabel: "Unlock",
    });

  challenge.displayUnlockError = unlock => {
    const errors = unlock && unlock.errors ? Object.values(unlock.errors) : [];
    return voyageAlert(errors.join("\n") || "Something went wrong. Please try again.", {
      title: "Can't unlock that",
    });
  };
};
