import React from "react";
import { Link } from "react-router-dom";
import { local_websocket } from "./utils.js";

class RunPage extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      ws: local_websocket("/ws/logs/" + this.props.match.params.run_id),
    };
    this.stopRun = this.stopRun.bind(this);
  }

  stopRun() {
    const outerThis = this;
    fetch("/api/run/" + this.props.match.params.run_id + "/stop", {
      method: "POST",
    })
      .then((response) => response.json())
      .then(function (data) {});
  }

  componentDidMount() {
    this.state.ws.onmessage = (evt) => {
      const message = JSON.parse(evt.data);
      this.setState(message);
    };

    fetch("/api/run/" + this.props.match.params.run_id)
      .then((response) => response.json())
      .then((data) => this.setState(data));
  }

  render() {
    return (
      <section className="section">
        <div className="container">
          <h1 className="title is-2">
            <Link to={"/task/" + this.state.task}>{this.state.task}</Link>:{" "}
            {this.state.uuid}
          </h1>

          {this.state.status == "Running" ? (
            <a className="button is-danger is-centered" onClick={this.stopRun}>
              Stop
            </a>
          ) : (
            ""
          )}

          <a className="button is-centered" href="#bottom">
            Latest Output
          </a>

          <table className="table">
            <tbody>
              <tr>
                <th>Status</th>
                <td>{this.state.status}</td>
              </tr>
              <tr>
                <th>Start</th>
                <td>{this.state.start}</td>
              </tr>
              <tr>
                <th>Exit Code</th>
                <td>{this.state.exit_code}</td>
              </tr>
            </tbody>
          </table>

          <pre>{this.state.logs}</pre>
          <a name="bottom"></a>
        </div>
      </section>
    );
  }
}

export default RunPage;
