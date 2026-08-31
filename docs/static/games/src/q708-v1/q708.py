"""q708 Escapement Evidence -- use exclusive interventions to localize a clock fault."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,WEIGHT,PROBE,CLUE,PHASE,GOAL,BAD=1,11,7,14,6,12,9,13,15
LEVELS=[{"name":"Passive Tick","seq":(1,)},{"name":"Opposed Weight","seq":(2,1)},{"name":"Exclusive Probe","seq":(3,1,2)},{"name":"Nested Phase","seq":(4,3,2,1)},{"name":"Fault Margin","seq":(2,3,1,4,2,3)},{"name":"Escapement Evidence","seq":(3,1,4,2,3,2,1,4,3)}]
def advance(s,a):
 phase,fault,evidence,margin,cost,interventions,stopped=s
 if a==1:w=1+phase%2;margin+=w if fault in (0,phase%3) else -1;evidence=evidence+((phase,w,1),);cost+=1;phase=(phase+1)%6
 elif a==2:w=1+(phase+1)%3;margin-=w if fault==2 else -1;evidence=evidence+((phase,w,-1),);cost+=2;phase=(phase+2)%6
 elif a==3:outcome=(phase+fault+len(interventions))%3;interventions=interventions+(outcome,);margin+=2-outcome;fault=(fault+outcome+1)%3
 elif a==4:phase=(phase+3)%6;margin+=1 if phase in (1,4) else 0
 elif a==5:stopped=(phase,fault,evidence[-4:],margin,cost,interventions[-3:])
 return phase,fault,evidence,margin,cost,interventions,stopped
for x in LEVELS:
 s=(0,0,(),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for i in range(3):x=9+i*17;f[8+i*3:29,x:x+12]=GEAR;f[20-(g.phase+i)%5*2:28,x+3:x+9]=WEIGHT;f[10:14,x+4:x+8]=PROBE if i==g.fault else PHASE
  for i,(_,w,sign) in enumerate(g.evidence[-4:]):x=8+i*12;f[35:42,x:x+9]=CLUE if sign>0 else PROBE;f[43:46,x:x+2+w*2]=WEIGHT
  for i,v in enumerate(g.interventions[-3:]):f[48:52,8+i*14:18+i*14]=PROBE if v else CLUE
  f[55:59,8:8+g.phase*8+7]=PHASE
  if g.stopped:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q708(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q708",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phase=self.fault=self.margin=self.cost=0;self.evidence=self.interventions=();self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.phase,self.fault,self.evidence,self.margin,self.cost,self.interventions,self.stopped=advance((self.phase,self.fault,self.evidence,self.margin,self.cost,self.interventions,self.stopped),a)
  elif a==6:
   if (self.phase,self.fault,self.evidence,self.margin,self.cost,self.interventions,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
