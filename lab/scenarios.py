"""Versioned synthetic environments and observation errors; no controller imports."""
import hashlib
import json
import math
import random

SCHEMA=1
SHAPES=('layer','tilted','front','patch','combined')
DEFAULT_POLICY=dict(tau_nominal_s=2.,tau_max_s=2.5,epsilon_c=.1,noise_assumed_c=.005,
                    primary_baseline='medium',gradient_threshold_cpm=2.,bin_m=.025,
                    boundary_error_cap_m=.30,boundary_miss_penalty_m=.30,
                    required_depth_range_m=[.1,.9],boundary_search_m=[.2,.8])
DEFAULT_ERRORS=dict(noise_rho=0.,temperature_bias_c=0.,temperature_drift_c_sqrt_s=0.,
                    temperature_quantum_c=0.,position_sigma_m=0.,position_bias_m=0.,
                    position_drift_m_s=0.,velocity_sigma_mps=0.,dropout_probability=0.,
                    dropout_burst_steps=0,jitter_ms=0,boundary_drift_mps=0.,probe_offset_m=0.,
                    calibrated_probe_offset_m=0.,flow_tau_factor=0.,acceleration_bias=0.,
                    thrust_gain=1.2,drag=1.5,ascent_gain=1.)


def stream_seed(seed,label):
    return int.from_bytes(hashlib.sha256(f'{seed}:{label}'.encode()).digest()[:8],'big')


def scenario(params,seed,split='development',errors=None):
    if split not in ('development','evaluation','deterministic'):raise ValueError('Invalid scenario split')
    field={k:params[k] for k in ('center','width','drop','shape','profile_x')}
    values=dict(DEFAULT_ERRORS,**(errors or {}))
    result=dict(schema=SCHEMA,id=f'{split}-{seed}',seed=int(seed),split=split,
                field=field,true_tau_s=float(params['tau']),noise_sigma_c=float(params['noise']),errors=values)
    validate(result)
    return result


def validate(s):
    if s['schema']!=SCHEMA:raise ValueError('Unsupported scenario schema')
    f=s['field'];e=s['errors']
    if not all(math.isfinite(float(f[k])) for k in ('center','width','drop','profile_x')) or not 0<=f['center']<=3 or not .5<=f['profile_x']<=7.5:raise ValueError('Invalid field coordinates')
    if f['shape'] not in SHAPES or not .01<=float(f['width'])<=.3 or not 0<=float(f['drop'])<=8:raise ValueError('Invalid field')
    if not .1<=s['true_tau_s']<=8 or not 0<=s['noise_sigma_c']<=.5:raise ValueError('Invalid probe')
    if set(e)!=set(DEFAULT_ERRORS) or not all(math.isfinite(float(v)) for v in e.values()):raise ValueError('Invalid observation errors')
    if not -.99<=e['noise_rho']<=.99 or not 0<=e['dropout_probability']<=1 or not 0<=e['dropout_burst_steps']<=50 or not 0<=e['jitter_ms']<=20:raise ValueError('Invalid acquisition errors')
    for key in ('position_sigma_m','velocity_sigma_mps','temperature_drift_c_sqrt_s','temperature_quantum_c','flow_tau_factor'):
        if not 0<=e[key]<=1:raise ValueError('Invalid '+key)
    if not .3<=e['thrust_gain']<=3 or not .3<=e['drag']<=4 or not .3<=e['ascent_gain']<=2:raise ValueError('Invalid plant')


def generate(params,count,seed,split='development',varied=False,errors=None):
    if not 1<=int(count)<=500 or int(count)!=count:raise ValueError('Scenario count must be 1–500')
    namespace=stream_seed(seed,split)
    scenarios=[]
    for index in range(int(count)):
        scenario_seed=stream_seed(namespace,str(index))%(2**31)
        p=dict(params);err=dict(errors or {})
        if varied:
            rng=random.Random(scenario_seed)
            p.update(center=rng.uniform(.3,.7),width=rng.choice([.025,.05,.1]),
                     drop=rng.choice([0.,1.,3.,5.]),tau=rng.choice([.3,1.,2.,4.]),
                     noise=rng.choice([0.,.02,.05,.1]),shape='layer')
            err.update(position_sigma_m=rng.choice([0.,.01,.04]),noise_rho=rng.choice([0.,.7]),
                       boundary_drift_mps=rng.choice([0.,0.,-.001,.001]),jitter_ms=rng.choice([0,10]),
                       temperature_bias_c=rng.choice([0.,-.1,.1]),dropout_probability=rng.choice([0.,.02]))
        scenarios.append(scenario(p,scenario_seed,split,err))
    return scenarios


def temperature(x,z,t,s):
    f=s['field'];center=f['center']+s['errors']['boundary_drift_mps']*t
    width=f['width'];drop=f['drop'];shape=f['shape']
    if shape=='front':return 22-drop/2*(1+math.tanh((x-4)/(5*width)))
    slope=.16 if shape in ('tilted','combined') else 0
    value=22-drop/2*(1+math.tanh((z-center-slope*(x-4))/width))
    if shape in ('patch','combined'):
        value+=2*math.exp(-.5*(((x-5.3)/.75)**2+((z-center-.35)/.3)**2))
    return value


def gradient(x,z,t,s):
    h=.0001
    return (temperature(x,z+h,t,s)-temperature(x,z-h,t,s))/(2*h)


def boundary(t,s):
    f=s['field']
    if f['drop']<=.001 or f['shape'] in ('front','patch','combined'):return None
    return f['center']+s['errors']['boundary_drift_mps']*t+(.16*(f['profile_x']-4) if f['shape']=='tilted' else 0)


class ObservationPipeline:
    """Independent digital errors; probe's thermal state stays noise-free."""
    def __init__(self,s,method):
        self.scenario=s;self.errors=s['errors'];self.noise=0.;self.drift=0.;self.burst=0
        self.measurement_rng=random.Random(stream_seed(s['seed'],'measurement:'+method))
        self.channel_rng=random.Random(stream_seed(s['seed'],'channel'))
        self.clock_rng=random.Random(stream_seed(s['seed'],'clock'))
    def interval_ms(self):
        return 50+self.clock_rng.randint(-int(self.errors['jitter_ms']),int(self.errors['jitter_ms']))
    def observe(self,ms,probe,z,v,dt):
        e=self.errors;rng=self.measurement_rng
        rho=e['noise_rho'];sigma=self.scenario['noise_sigma_c']
        self.noise=rho*self.noise+sigma*math.sqrt(1-rho*rho)*rng.gauss(0,1)
        self.drift+=e['temperature_drift_c_sqrt_s']*math.sqrt(dt)*rng.gauss(0,1)
        y=probe+self.noise+self.drift+e['temperature_bias_c']
        if e['temperature_quantum_c']>0:y=round(y/e['temperature_quantum_c'])*e['temperature_quantum_c']
        estimated_z=z+e['position_bias_m']+e['position_drift_m_s']*ms/1000+e['position_sigma_m']*rng.gauss(0,1)
        estimated_v=v+e['velocity_sigma_mps']*rng.gauss(0,1)
        if self.burst:self.burst-=1;return None
        if self.channel_rng.random()<e['dropout_probability']:
            self.burst=int(e['dropout_burst_steps']);return None
        return dict(acquired_ms=ms,temperature_c=y,depth_m=estimated_z,velocity_mps=estimated_v)


def policy_digest(policy):
    return hashlib.sha256(json.dumps(policy,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
