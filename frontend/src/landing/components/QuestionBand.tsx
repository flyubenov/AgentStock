import { QUESTION_BAND } from '../content/framework'

/** Bridges the live result above to the Framework's explanation below (spec 5.4).
 *  A div, not a section: it is not a nav destination. */
export default function QuestionBand() {
  return (
    <div className="qband">
      <div className="container">
        <h2>{QUESTION_BAND.title}</h2>
        <p>{QUESTION_BAND.body}</p>
      </div>
    </div>
  )
}
