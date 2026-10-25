import "./main";
import $ from "jquery";
import dayjs from "dayjs";
import "../compat/json";
import "bootstrap/js/dist/tab";
import CTFd from "../compat/CTFd";
import { htmlEntities } from "@ctfdio/ctfd-js/utils/html";
import { ezQuery, ezAlert, ezToast } from "../compat/ezq";
import { default as helpers } from "../compat/helpers";
import { bindMarkdownEditors } from "../styles";
import Vue from "vue";
import CommentBox from "../components/comments/CommentBox.vue";
import FlagList from "../components/flags/FlagList.vue";
import Requirements from "../components/requirements/Requirements.vue";
import TopicsList from "../components/topics/TopicsList.vue";
import TagsList from "../components/tags/TagsList.vue";
import ChallengeFilesList from "../components/files/ChallengeFilesList.vue";
import HintsList from "../components/hints/HintsList.vue";
import NextChallenge from "../components/next/NextChallenge.vue";
import SolutionEditor from "../components/solution/SolutionEditor.vue";
import RatingsViewer from "../components/ratings/RatingsViewer.vue";

function loadChalTemplate(challenge) {
  CTFd._internal.challenge = {};
  $.getScript(CTFd.config.urlRoot + challenge.scripts.view, function () {
    let template_data = challenge.create;
    $("#create-chal-entry-div").html(template_data);
    bindMarkdownEditors();

    $.getScript(CTFd.config.urlRoot + challenge.scripts.create, function () {
      $("#create-chal-entry-div form").submit(function (event) {
        event.preventDefault();
        const params = $("#create-chal-entry-div form").serializeJSON();
        CTFd.fetch("/api/v1/challenges", {
          method: "POST",
          credentials: "same-origin",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify(params),
        })
          .then(function (response) {
            return response.json();
          })
          .then(function (response) {
            if (response.success) {
              $("#challenge-create-options #challenge_id").val(
                response.data.id,
              );
              $("#challenge-create-options").modal();
            } else {
              let body = "";
              for (const k in response.errors) {
                body += response.errors[k].join("\n");
                body += "\n";
              }

              ezAlert({
                title: "Error",
                body: body,
                button: "OK",
              });
            }
          });
      });
    });
  });
}

function handleChallengeOptions(event) {
  event.preventDefault();
  var params = $(event.target).serializeJSON(true);
  let flag_params = {
    challenge_id: params.challenge_id,
    content: params.flag || "",
    type: params.flag_type,
    data: params.flag_data ? params.flag_data : "",
  };
  if (params.flag_type === "dynamic") {
    // Send the key shown in the form so it matches the AI-agent prompt
    flag_params.data = JSON.stringify({
      secret: (params.flag_secret || "").trim(),
    });
  }
  // Define a save_challenge function
  let save_challenge = function () {
    CTFd.fetch("/api/v1/challenges/" + params.challenge_id, {
      method: "PATCH",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        state: params.state,
      }),
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.success) {
          setTimeout(function () {
            window.location =
              CTFd.config.urlRoot + "/admin/challenges/" + params.challenge_id;
          }, 700);
        }
      });
  };

  Promise.all([
    // Save flag
    new Promise(function (resolve, _reject) {
      if (flag_params.content.length == 0) {
        resolve();
        return;
      }
      CTFd.fetch("/api/v1/flags", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(flag_params),
      }).then(function (response) {
        resolve(response.json());
      });
    }),
    // Upload files
    new Promise(function (resolve, _reject) {
      let form = event.target;
      let data = {
        challenge: params.challenge_id,
        type: "challenge",
      };
      let filepath = $(form.elements["file"]).val();
      if (filepath) {
        helpers.files.upload(form, data);
      }
      resolve();
    }),
  ]).then((responses) => {
    // Don't move on with a challenge whose flag failed to save
    const flagResponse = responses[0];
    if (flagResponse && !flagResponse.success) {
      ezAlert({
        title: "Flag not saved",
        body: Object.values(flagResponse.errors || {}).join("<br>"),
        button: "OK",
      });
      return;
    }
    save_challenge();
  });
}

const SCHEDULE_TOOLTIPS = {
  scheduled: "Becomes visible to users at {time}.",
  hidden: "This challenge is hidden. Scheduling will not make it visible.",
};

// The API serializes scheduled_at as a naive UTC timestamp, so mark it as UTC
// before parsing or dayjs would read it as local time.
function parseScheduledAt(value) {
  return dayjs(/(Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : value + "Z");
}

// Mirrors the challenge_state_badge macro so that the badge
// stays accurate after saving without requiring a page reload.
function updateChallengeStateBadge(state, scheduledAt) {
  const pending =
    state === "visible" &&
    scheduledAt &&
    parseScheduledAt(scheduledAt).isAfter(dayjs());
  const displayState = pending ? "scheduled" : state;
  const badgeClass =
    { scheduled: "badge-warning", hidden: "badge-danger" }[displayState] ||
    "badge-success";

  const $badge = $(".challenge-state");
  $badge.tooltip("dispose");
  $badge
    .removeClass("badge-success badge-danger badge-warning")
    .addClass(badgeClass)
    .text(displayState);

  const note = scheduledAt ? SCHEDULE_TOOLTIPS[displayState] : undefined;
  if (note) {
    // Only the scheduled note names a time
    if (displayState === "scheduled") {
      $badge.attr("data-schedule-time", scheduledAt);
    } else {
      $badge.removeAttr("data-schedule-time");
    }
    $badge
      .attr("data-toggle", "tooltip")
      .attr("data-placement", "top")
      .attr(
        "title",
        note.replace(
          "{time}",
          parseScheduledAt(scheduledAt).format("MMMM Do, h:mm:ss A"),
        ),
      )
      .tooltip();
  } else {
    $badge
      .removeAttr("data-toggle")
      .removeAttr("data-placement")
      .removeAttr("data-schedule-time")
      .removeAttr("data-original-title")
      .removeAttr("title");
  }
}

$(() => {
  $(".preview-challenge").click(function (_e) {
    let url = `${CTFd.config.urlRoot}/admin/challenges/preview/${window.CHALLENGE_ID}`;
    $("#challenge-window").html(
      `<iframe src="${url}" height="100%" width="100%" frameBorder=0></iframe>`,
    );
    $("#challenge-modal").modal();
  });

  $(".comments-challenge").click(function (_event) {
    $("#challenge-comments-window").modal();
  });

  $(".ratings-challenge").click(function (_event) {
    $("#challenge-ratings-window").modal();
  });

  $(".delete-challenge").click(function (_e) {
    ezQuery({
      title: "Delete Challenge",
      body: `Are you sure you want to delete <strong>${htmlEntities(
        window.CHALLENGE_NAME,
      )}</strong>`,
      success: function () {
        CTFd.fetch("/api/v1/challenges/" + window.CHALLENGE_ID, {
          method: "DELETE",
        })
          .then(function (response) {
            return response.json();
          })
          .then(function (response) {
            if (response.success) {
              window.location = CTFd.config.urlRoot + "/admin/challenges";
            }
          });
      },
    });
  });

  $(".chal-scheduled-at").each(function () {
    const $input = $(this);
    const utc = $input.data("scheduled-at-utc");
    if (utc) {
      $input.val(dayjs(utc).format("YYYY-MM-DDTHH:mm:ss"));
    }

    $input.data("initial", $input.val());
  });

  $("#challenge-update-container > form").submit(function (e) {
    e.preventDefault();
    var params = $(e.target).serializeJSON(true);

    if ("scheduled_at" in params) {
      const raw = params.scheduled_at;
      params.scheduled_at = raw ? dayjs(raw).toISOString() : null;
    }

    CTFd.fetch("/api/v1/challenges/" + window.CHALLENGE_ID + "/flags", {
      method: "GET",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (response) {
        let update_challenge = function () {
          CTFd.fetch("/api/v1/challenges/" + window.CHALLENGE_ID, {
            method: "PATCH",
            credentials: "same-origin",
            headers: {
              Accept: "application/json",
              "Content-Type": "application/json",
            },
            body: JSON.stringify(params),
          })
            .then(function (response) {
              return response.json();
            })
            .then(function (response) {
              if (response.success) {
                updateChallengeStateBadge(
                  response.data.state,
                  response.data.scheduled_at,
                );
                ezToast({
                  title: "Success",
                  body: "Your challenge has been updated!",
                });
              } else {
                let body = "";
                for (const k in response.errors) {
                  body += response.errors[k].join("\n");
                  body += "\n";
                }

                ezAlert({
                  title: "Error",
                  body: body,
                  button: "OK",
                });
              }
            });
        };
        // Check if the challenge doesn't have any flags before marking visible
        if (response.data.length === 0 && params.state === "visible") {
          ezQuery({
            title: "Missing Flags",
            body: "This challenge does not have any flags meaning it may be unsolveable. Are you sure you'd like to update this challenge?",
            success: update_challenge,
          });
        } else {
          update_challenge();
        }
      });
  });

  $("#challenge-create-options form").submit(handleChallengeOptions);

  // Static / Dynamic flag choice in the create options modal
  let generatedKey = "";
  let promptTimer = null;
  const randomKey = function () {
    const bytes = new Uint8Array(32);
    window.crypto.getRandomValues(bytes);
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  };
  const copyField = function (button, field) {
    const done = () => {
      $(button).text("Copied");
      setTimeout(() => $(button).text(button.dataset.label), 1500);
    };
    button.dataset.label = button.dataset.label || $(button).text();
    field.select();
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(field.value).then(done);
    } else {
      document.execCommand("copy");
      done();
    }
  };
  const loadAgentPrompt = function () {
    clearTimeout(promptTimer);
    promptTimer = setTimeout(() => {
      CTFd.fetch("/api/v1/flags/agent-prompt", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          content: $("#flag-input").val(),
          data: { secret: $("#flag-secret").val().trim() },
        }),
      })
        .then((response) => response.json())
        .then((response) => {
          if (response.success) {
            $("#flag-prompt").val(response.data.prompt);
            const warnings = response.data.warnings || [];
            $("#flag-dynamic-warnings")
              .text(warnings.join(" "))
              .toggleClass(
                "d-none",
                !warnings.length || !$("#flag-type-dynamic").is(":checked"),
              );
          }
        });
    }, 300);
  };
  const syncFlagOptions = function (event) {
    const dynamic = $("#flag-type-dynamic").is(":checked");
    const ownKey = $("#flag-key-own").is(":checked");
    const flag = $("#flag-input");
    const secret = $("#flag-secret");

    $("#flag-case-col").toggleClass("d-none", dynamic);
    $("#flag-input-col").toggleClass("col-md-8", !dynamic);
    $("#flag-input-col").toggleClass("col-md-12", dynamic);
    $("#flag-key-group").toggleClass("d-none", !dynamic);
    $("#flag-dynamic-example").toggleClass("d-none", !dynamic);
    $("#flag-help").text(
      dynamic
        ? "Each team must submit this flag with their own unique suffix"
        : "Static flag for your challenge",
    );
    flag.attr("placeholder", dynamic ? "cc10{w4x_h1d}" : "");
    flag.prop("required", dynamic);

    // Show where the per-team suffix will go
    const base = flag.val().trim() || "cc10{w4x_h1d}";
    const tag = "3fa9c0b17e";
    let example;
    if (base.includes("%TAG%")) {
      example = base.split("%TAG%").join(tag);
    } else if (base.lastIndexOf("}") === -1) {
      example = `${base}_${tag}`;
    } else {
      const i = base.lastIndexOf("}");
      example = `${base.slice(0, i)}_${tag}${base.slice(i)}`;
    }
    $("#flag-dynamic-preview").text(example);

    // Generated keys are made here so the prompt shows the key that gets saved
    if (dynamic && !generatedKey) {
      generatedKey = randomKey();
    }
    const switchedMode = event && event.target.name === "flag_key_mode";
    if (switchedMode) {
      secret.val(ownKey ? "" : generatedKey);
    } else if (!ownKey) {
      secret.val(generatedKey);
    }
    secret.prop("readonly", !ownKey);
    secret.prop("required", dynamic);
    secret.attr(
      "placeholder",
      ownKey ? "Hex key, e.g. the challenge server's secret.key" : "",
    );
    $("#flag-key-help").text(
      ownKey
        ? "The backend will use exactly this key. Give the same key to your challenge server."
        : "A new random key for this challenge. Give it to your challenge server.",
    );
    $("#flag-prompt-group").toggleClass("d-none", !dynamic);
    if (!dynamic) {
      $("#flag-dynamic-warnings").addClass("d-none");
    }
    const key = secret.val().trim();
    const valid = !(dynamic && ownKey) || /^([0-9a-fA-F]{2})+$/.test(key);
    secret[0].setCustomValidity(
      valid ? "" : "Key must be hex (0-9, a-f), an even number of characters",
    );
    secret.toggleClass("is-invalid", key !== "" && !valid);

    if (dynamic) {
      loadAgentPrompt();
    }
  };
  $(
    "#challenge-create-options input[name=flag_type], #challenge-create-options input[name=flag_key_mode]",
  ).change(syncFlagOptions);
  $("#flag-input, #flag-secret").on("input", syncFlagOptions);
  $("#flag-secret-copy").click(function () {
    copyField(this, $("#flag-secret")[0]);
  });
  $("#flag-prompt-copy").click(function () {
    copyField(this, $("#flag-prompt")[0]);
  });

  $(".chal-function")
    .change(function () {
      const selectedFunction = $(this).val();
      const initialFormGroup = $(".chal-initial").closest(".form-group");
      const decayFormGroup = $(".chal-decay").closest(".form-group");
      const minimumFormGroup = $(".chal-minimum").closest(".form-group");
      const initialInput = $(".chal-initial");
      const decayInput = $(".chal-decay");
      const minimumInput = $(".chal-minimum");
      const valueInput = $(".chal-value");

      if (selectedFunction === "static") {
        // Save current values to data attributes before clearing them
        if (initialInput.val()) {
          initialInput.data("saved-value", initialInput.val());
        }
        if (decayInput.val()) {
          decayInput.data("saved-value", decayInput.val());
        }
        if (minimumInput.val()) {
          minimumInput.data("saved-value", minimumInput.val());
        }

        // Clear the input values to prevent validation errors on hidden fields
        initialInput.val("");
        decayInput.val("");
        minimumInput.val("");

        // Hide initial, decay, and minimum form groups for static function
        initialFormGroup.hide();
        decayFormGroup.hide();
        minimumFormGroup.hide();

        // Remove name attributes so they won't be included in serializeJSON
        initialInput.removeAttr("name").data("original-name", "initial");
        decayInput.removeAttr("name").data("original-name", "decay");
        minimumInput.removeAttr("name").data("original-name", "minimum");

        // Remove required attribute for static function
        initialInput.removeAttr("required");
        decayInput.removeAttr("required");
        minimumInput.removeAttr("required");

        // Make value input enabled and required for static function
        valueInput.prop("disabled", false).prop("required", true);
      } else if (
        selectedFunction === "linear" ||
        selectedFunction === "logarithmic"
      ) {
        // Show initial, decay, and minimum form groups for linear and logarithmic functions
        initialFormGroup.show();
        decayFormGroup.show();
        minimumFormGroup.show();

        // Restore name attributes so they will be included in serializeJSON
        initialInput.attr(
          "name",
          initialInput.data("original-name") || "initial",
        );
        decayInput.attr("name", decayInput.data("original-name") || "decay");
        minimumInput.attr(
          "name",
          minimumInput.data("original-name") || "minimum",
        );

        // Restore saved values from data attributes
        if (initialInput.data("saved-value")) {
          initialInput.val(initialInput.data("saved-value"));
        }
        if (decayInput.data("saved-value")) {
          decayInput.val(decayInput.data("saved-value"));
        }
        if (minimumInput.data("saved-value")) {
          minimumInput.val(minimumInput.data("saved-value"));
        }

        // Add required attribute for dynamic functions
        initialInput.prop("required", true);
        decayInput.prop("required", true);
        minimumInput.prop("required", true);

        // Make value input disabled and not required for dynamic functions
        valueInput.prop("disabled", true).prop("required", false);
      }
    })
    .trigger("change"); // Trigger change event on page load to set initial state

  // Load FlagList component
  if (document.querySelector("#challenge-flags")) {
    const flagList = Vue.extend(FlagList);
    let vueContainer = document.createElement("div");
    document.querySelector("#challenge-flags").appendChild(vueContainer);
    new flagList({
      propsData: { challenge_id: window.CHALLENGE_ID },
    }).$mount(vueContainer);
  }

  // Load TopicsList component
  if (document.querySelector("#challenge-topics")) {
    const topicsList = Vue.extend(TopicsList);
    let vueContainer = document.createElement("div");
    document.querySelector("#challenge-topics").appendChild(vueContainer);
    new topicsList({
      propsData: { challenge_id: window.CHALLENGE_ID },
    }).$mount(vueContainer);
  }

  // Load TagsList component
  if (document.querySelector("#challenge-tags")) {
    const tagList = Vue.extend(TagsList);
    let vueContainer = document.createElement("div");
    document.querySelector("#challenge-tags").appendChild(vueContainer);
    new tagList({
      propsData: { challenge_id: window.CHALLENGE_ID },
    }).$mount(vueContainer);
  }

  // Load Requirements component
  if (document.querySelector("#prerequisite-add-form")) {
    const reqsComponent = Vue.extend(Requirements);
    let vueContainer = document.createElement("div");
    document.querySelector("#prerequisite-add-form").appendChild(vueContainer);
    new reqsComponent({
      propsData: { challenge_id: window.CHALLENGE_ID },
    }).$mount(vueContainer);
  }

  // Load ChallengeFilesList component
  if (document.querySelector("#challenge-files")) {
    const challengeFilesList = Vue.extend(ChallengeFilesList);
    let vueContainer = document.createElement("div");
    document.querySelector("#challenge-files").appendChild(vueContainer);
    new challengeFilesList({
      propsData: { challenge_id: window.CHALLENGE_ID },
    }).$mount(vueContainer);
  }

  // Load HintsList component
  if (document.querySelector("#challenge-hints")) {
    const hintsList = Vue.extend(HintsList);
    let vueContainer = document.createElement("div");
    document.querySelector("#challenge-hints").appendChild(vueContainer);
    new hintsList({
      propsData: { challenge_id: window.CHALLENGE_ID },
    }).$mount(vueContainer);
  }

  // Load Next component
  if (document.querySelector("#next-add-form")) {
    const nextChallenge = Vue.extend(NextChallenge);
    let vueContainer = document.createElement("div");
    document.querySelector("#next-add-form").appendChild(vueContainer);
    new nextChallenge({
      propsData: { challenge_id: window.CHALLENGE_ID },
    }).$mount(vueContainer);
  }

  // Load SolutionEditor component
  if (document.querySelector("#challenge-solution")) {
    const solutionEditor = Vue.extend(SolutionEditor);
    let vueContainer = document.createElement("div");
    document.querySelector("#challenge-solution").appendChild(vueContainer);
    new solutionEditor({
      propsData: {
        challenge_id: window.CHALLENGE_ID,
      },
    }).$mount(vueContainer);
  }

  // Because this JS is shared by a few pages,
  // we should only insert the CommentBox if it's actually in use
  if (document.querySelector("#comment-box")) {
    // Insert CommentBox element
    const commentBox = Vue.extend(CommentBox);
    let vueContainer = document.createElement("div");
    document.querySelector("#comment-box").appendChild(vueContainer);
    new commentBox({
      propsData: { type: "challenge", id: window.CHALLENGE_ID },
    }).$mount(vueContainer);
  }

  // Load RatingsViewer component
  if (document.querySelector("#ratings-box")) {
    const ratingsViewer = Vue.extend(RatingsViewer);
    let vueContainer = document.createElement("div");
    document.querySelector("#ratings-box").appendChild(vueContainer);
    new ratingsViewer({
      propsData: { challengeId: window.CHALLENGE_ID },
    }).$mount(vueContainer);
  }

  $.get(CTFd.config.urlRoot + "/api/v1/challenges/types", function (response) {
    const data = response.data;
    loadChalTemplate(data["standard"]);

    $("#create-chals-select input[name=type]").change(function () {
      let challenge = data[this.value];
      loadChalTemplate(challenge);
    });
  });
});
