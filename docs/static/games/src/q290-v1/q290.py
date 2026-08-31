"""q290 Workbench Probe -- diagnose a fixture and return borrowed help before repair."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BENCH,FIXTURE,TOOL,PROBE,EVIDENCE,DEBT,REPAIR,BAD=2,10,9,14,6,4,11,7,15
LEVELS=[{"name":"Direct Fixture","model":1,"budget":1,"plan":(1,4,5)},{"name":"Shared Arbor","model":2,"budget":4,"plan":(2,1,4,2,1,5)},{"name":"Coincident Tool","model":3,"budget":4,"plan":(1,3,4,1,3,5)},{"name":"Two Helpers","model":2,"budget":4,"plan":(2,4,3,4,2,5,3,5)},{"name":"Crossed Repair","model":3,"budget":7,"plan":(3,1,4,2,3,4,1,3,5,1,5)},{"name":"Workbench Probe","model":1,"budget":6,"plan":(1,2,4,3,4,1,3,5,2,5)}]
def advance(s,a,x):
 evidence,selected,debt,diagnostic,repair=s;evidence=list(evidence);debt=list(debt)
 if repair is not None:return None
 if a in (1,2,3):selected=a-1;evidence.append((a,(x["model"]*a+len(evidence)+sum(debt))%5))
 elif a==4:debt[selected]+=1;diagnostic=(x["model"],selected,tuple(evidence))
 elif a==5:
  if not debt[selected] or diagnostic is None:return None
  debt[selected]-=1
  if not sum(debt):repair=(x["model"],diagnostic,tuple(evidence))
 return tuple(evidence),selected,tuple(debt),diagnostic,repair
def target(x):
 s=((),0,(0,0,0),None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BENCH
  for i in range(3):x=8+i*18;f[8:31,x:x+14]=FIXTURE;f[13+i*4:19+i*4,x+4:x+10]=TOOL-i;f[33:36,x:x+g.debt[i]*6]=DEBT
  for i,(_,v) in enumerate(g.evidence[-6:]):f[39+i*3:41+i*3,8:11+v*10]=EVIDENCE
  f[54:57,8:24]=PROBE if g.diagnostic else FIXTURE;f[57:60,40:56]=REPAIR if g.repair else TOOL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q290(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q290",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.selected=0;self.debt=(0,0,0);self.diagnostic=self.repair=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   probes=len(self.evidence);s=advance((self.evidence,self.selected,self.debt,self.diagnostic,self.repair),a,x)
   if s is None or (a in (1,2,3) and probes>=x["budget"]):self.bad=True;self.lose()
   else:self.evidence,self.selected,self.debt,self.diagnostic,self.repair=s
  elif a==6:
   if (self.evidence,self.selected,self.debt,self.diagnostic,self.repair)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
