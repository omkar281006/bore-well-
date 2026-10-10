import { useEffect } from 'react';
import { SimProvider, useSim } from './hooks/SimProvider.jsx';
import { useTheme } from './hooks/useTheme.js';
import { ToastProvider } from './hooks/useToast.jsx';
import { Ambient, Intro } from './components/Effects.jsx';
import { Masthead, Ticker } from './components/Header.jsx';
import Stage from './components/Stage.jsx';
import ControlRail from './components/ControlRail.jsx';
import {
  AlertCard, DiagnosisCard, EchoCard, FleetCard, ForecastCard, HowItWorks, KpiRow, Last72Card, ParamsCard, RecoveryCard, SeasonCard,
} from './components/Dashboard.jsx';

function AlarmVignette() {
  const { sim } = useSim();
  const crit = (sim.findings[0] || {}).sev === 'crit';
  useEffect(() => {
    document.body.classList.toggle('alarm-on', crit);
  }, [crit]);
  return null;
}

export default function App() {
  const { isLight, toggle } = useTheme();
  return (
    <SimProvider>
      <ToastProvider>
        <Ambient />
        <Intro />
        <AlarmVignette />
        <div className="wrap">
          <Masthead isLight={isLight} onToggleTheme={toggle} />
          <Ticker />
          <div className="stage-row">
            <Stage isLight={isLight} />
            <ControlRail />
          </div>
          <KpiRow />
          <main className="dash">
            <ForecastCard />
            <DiagnosisCard />
            <SeasonCard />
            <AlertCard />
            <Last72Card />
            <RecoveryCard />
            <EchoCard />
            <FleetCard />
            <HowItWorks />
            <ParamsCard />
          </main>
          <p className="foot">
            All wells, readings and alerts are simulated. Aquifer ranges follow CGWB aquifer mapping of Pune district (deep basalt aquifer at 48–175 m, storativity ~10⁻⁴,
            pumping sustainable for 0.5–3 h). Rainfall is a synthetic Pune year. Built for AWS: Strands Agents, SAM, Lambda, Step Functions, SageMaker, DynamoDB and Amplify.
          </p>
        </div>
      </ToastProvider>
    </SimProvider>
  );
}
