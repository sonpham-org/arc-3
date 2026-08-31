"""q286 Crossing Probe -- combine controller evidence before an irreversible ferry repair."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,RIVER,DOCK,PASSENGER,PROBE,EVIDENCE,MARK,REPAIR,BAD=7,10,9,14,5,4,11,2,15
LEVELS=[{"name":"Direct Ferry","model":1,"budget":2,"plan":(1,3,5)},{"name":"Shared Dock","model":2,"budget":3,"plan":(2,3,4,1,3,5)},{"name":"Coincident Fare","model":3,"budget":4,"plan":(1,2,3,4,2,3,5)},{"name":"Split Diagnosis","model":2,"budget":4,"plan":(2,1,3,4,1,2,3,5)},{"name":"Remote Repair","model":3,"budget":4,"plan":(1,3,4,2,1,3,5)},{"name":"Crossing Probe","model":1,"budget":5,"plan":(2,1,3,4,1,2,3,5)}]
def result(model,a,controller):return (model*a+controller+1)%4
def advance(s,a,x):
 controller,evidence,marks,committed=s;evidence=list(evidence);marks=list(marks)
 if committed:return None
 if a in (1,2):evidence.append((controller,a,result(x["model"],a,controller)))
 elif a==3:marks[controller]=(sum(v for c,_,v in evidence if c==controller)+controller)%4
 elif a==4:controller=1-controller
 elif a==5:committed=(tuple(marks),tuple(evidence),x["model"])
 return controller,tuple(evidence),tuple(marks),committed
def target(x):
 s=(0,(),(0,0),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=RIVER
  for i in range(2):x=8+i*29;f[9:31,x:x+22]=DOCK;f[15:23,x+6:x+16]=PASSENGER-i
  for i,(_,_,v) in enumerate(g.evidence[-6:]):f[35+i*3:37+i*3,8:11+v*11]=EVIDENCE
  f[52:55,8:11+g.marks[g.controller]*11]=MARK;f[57:60,8:20]=REPAIR if g.committed else PROBE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q286(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q286",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=0;self.evidence=();self.marks=(0,0);self.committed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   probes=len(self.evidence);s=advance((self.controller,self.evidence,self.marks,self.committed),a,x)
   if s is None or (a in (1,2) and probes>=x["budget"]):self.bad=True;self.lose()
   else:self.controller,self.evidence,self.marks,self.committed=s
  elif a==6:
   if (self.controller,self.evidence,self.marks,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
