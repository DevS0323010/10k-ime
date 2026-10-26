import { layout, mapping } from "./maps.js";
import { en_rank } from "./ranker.js";

let text = "",
  buffer = "";

function update_buttons(layout_id, override = [[], []]) {
  for (let i = 0; i < 2; i++) {
    for (let j = 0; j < 5; j++) {
      document.getElementById("" + (i + 1) + j).innerText =
        (override.at(i).at(j) ?? "") == ""
          ? layout[layout_id][i][j]
          : override.at(i).at(j);
      console.log(layout[layout_id][i][j]);
    }
  }
}

function update_cands(res) {
  document.getElementById("buffer").innerText = text;
  for (let i = 0; i < (res.length <= 5 ? 5 : 4); i++) {
    if (i < res.length) document.getElementById("0" + i).innerText = res[i];
    else document.getElementById("0" + i).innerText = "-";
  }
}

function update(id) {
  const row = Number(id[0]),
    col = Number(id[1]);
  if (row == 0) {
    if (document.getElementById(id).innerText != "-") {
      text += document.getElementById(id).innerText + " ";
      buffer = "";
    }
  } else {
    const key = mapping["en"][row - 1][col];
    if (key.length == 1) buffer += key;
    if (key == "<<")
      if (buffer.length > 0) buffer = buffer.slice(0, -1);
      else if (text.length > 0) text = text.slice(0, -1);
  }
  if (buffer.length > 0) update_buttons("en", [["'-"], []]);
  else update_buttons("en");
  const res = en_rank(text.trim().split(" ").at(-1) ?? "", buffer);
  update_cands(res);
}

document.querySelectorAll(".btn").forEach((button) => {
  button.addEventListener("click", () => {
    update(button.id);
  });
});

document.addEventListener("DOMContentLoaded", async () => {
  update_buttons("en");
  const res = en_rank("", buffer);
  update_cands(res);
});
