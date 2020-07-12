import * as React from 'react'
import { render } from 'react-dom'

const listAllAPIEndpoint = '/api/all'

interface FuriganaRecord {
    word: string
    furigana: string
    meaning: string
    note: string
    ruby: string
}

interface TableProps {
    records: Array<FuriganaRecord>
}

class Table extends React.Component<TableProps> {
    render() {
        return <table>
            <thead>
                <tr>
                    <th>word</th>
                    <th>furigana</th>
                    <th>meaning</th>
                    <th>note</th>
                    <th>ruby</th>
                </tr>
            </thead>
            <tbody>
                {this.props.records.map(function (e) {
                    return (
                        <tr>
                            <td>{e.word}</td>
                            <td>{e.furigana}</td>
                            <td>{e.meaning}</td>
                            <td>{e.note}</td>
                            <td>{e.ruby}</td>
                        </tr>
                    )
                })}
            </tbody>
        </table>
    }
}

interface AppState {
    records: Array<FuriganaRecord>
}

class App extends React.Component<{}, AppState> {

    constructor(props: {}) {
        super(props)

        this.state = {
            records: [],
        }

        this.loadRecords = this.loadRecords.bind(this)
    }


    loadRecords() {
        let that = this
        let xhr = new XMLHttpRequest()
        xhr.addEventListener('load', function () {
            if (xhr.status == 200) {
                console.log(xhr)
                that.setState({
                    records: JSON.parse(xhr.responseText),
                })
            }
        })

        xhr.open('POST', listAllAPIEndpoint)
        xhr.send()
    }


    render() {
        return <div>
            <div>
                <button onClick={() => this.loadRecords()}>Load Records</button>
            </div>
            <div><Table records={this.state.records} /></div>
        </div>
    }
}

render(<App />, document.getElementById('app'))
