"""a071 Event Sampler -- conserve a tiny battery with triggered observations."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FIELD,CELL,CHANGE,INDICATOR,BATTERY,SAMPLE,ARMED,TRACE,BAD=15,8,9,12,14,10,13,11,6,4
LEVELS=[
 {"name":"Periodic Probe","seq":(2,)},{"name":"Watch Indicator","seq":(1,3)},
 {"name":"Triggered Sample","seq":(3,1,4)},{"name":"Rare Change","seq":(1,3,1,1,4)},
 {"name":"Conserve Battery","seq":(3,1,1,4,1,3,4)},{"name":"Event Sampler","seq":(1,3,1,4,1,1,3,1,4,1)},
]
def advance(s,a):
 cells,clock,battery,indicator,armed,observed,events,history,snapshot=s;c=list(cells)
 if a==1:
  clock+=1
  if clock%3==0:i=(clock//3)%6;c[i]^=1;indicator=1;events=(events+(i,))[-5:]
  history=(history+(1,))[-8:]
 elif a==2:
  if battery:battery-=1;observed=tuple(c);indicator=0
  history=(history+(2,))[-8:]
 elif a==3:armed^=1;history=(history+(3,))[-8:]
 elif a==4:
  if armed and indicator and battery:battery-=1;observed=tuple(c);indicator=0;armed=0
  history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(c),clock,battery,indicator,armed,observed,events,history)
 return tuple(c),clock,battery,indicator,armed,observed,events,history,snapshot
for x in LEVELS:
 s=((0,1,0,1,1,0),0,4,0,0,(0,1,0,1,1,0),(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i,v in enumerate(g.observed):x=8+(i%3)*16;y=13+(i//3)*19;f[y:y+14,x:x+13]=CHANGE if v else CELL
  f[7:11,8:8+g.battery*10]=BATTERY;f[8:15,50:57]=INDICATOR if g.indicator else TRACE
  if g.armed:f[47:52,8:30]=ARMED
  for i,e in enumerate(g.events):f[54:58,33+i*5:37+i*5]=SAMPLE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A071(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a071",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cells,self.clock,self.battery,self.indicator,self.armed,self.observed,self.events,self.history,self.snapshot=((0,1,0,1,1,0),0,4,0,0,(0,1,0,1,1,0),(),(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.cells,self.clock,self.battery,self.indicator,self.armed,self.observed,self.events,self.history,self.snapshot=advance((self.cells,self.clock,self.battery,self.indicator,self.armed,self.observed,self.events,self.history,self.snapshot),a)
  elif a==6:
   if (self.cells,self.clock,self.battery,self.indicator,self.armed,self.observed,self.events,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
