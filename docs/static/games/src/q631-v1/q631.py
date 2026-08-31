"""q631 Tapestry Sandbox -- test reversible looms, retain evidence, then commit once."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LOOM,THREAD,SHUTTLE,MINI,EVIDENCE,GRAPH,GOAL,BAD=5,10,9,14,7,6,12,13,15
LEVELS=[{"name":"Miniature Trial","seq":(1,3)},{"name":"Reset Shuttle","seq":(2,3,4)},{"name":"Persistent Threadmark","seq":(1,3,4,2,3)},{"name":"Rewired Copy","seq":(2,1,3,4,1,3)},{"name":"Contrast Two Looms","seq":(1,2,3,4,2,2,3)},{"name":"Tapestry Sandbox","seq":(2,1,3,4,1,2,3,4,2,3)}]
def advance(s,a):
 main,sim,graph,evidence,trials,commit=s;v=list(sim)
 if a==1:v[0],v[1]=v[1],v[0];graph=(graph+1+v[0])%4
 elif a==2:v=v[1:]+v[:1];graph=(graph+2+v[1])%4
 elif a==3:evidence=evidence+((tuple(v),graph),);trials+=1
 elif a==4:v=list(main);graph=0
 elif a==5:main=tuple(v);graph=(graph+sum(v)+len(evidence))%4;commit=(main,graph,evidence[-4:],trials)
 return tuple(main),tuple(v),graph,evidence,trials,commit
for x in LEVELS:
 s=((0,1,2),(0,1,2),0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LOOM;f[8:31,7:29]=THREAD;f[8:31,35:57]=MINI
  for side,vals in enumerate((g.main,g.sim)):
   for i,v in enumerate(vals):x=9+side*28+i*6;f[23-v*4:29,x:x+5]=SHUTTLE
  for i,(vals,z) in enumerate(g.evidence[-5:]):x=8+i*10;f[36:42,x:x+7]=EVIDENCE;f[43:46,x:x+2+z]=GRAPH
  f[51:55,8:8+g.graph*12+9]=GRAPH;f[56:59,8:8+min(5,g.trials)*9]=EVIDENCE
  if g.commit:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q631(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q631",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.main=self.sim=(0,1,2);self.graph=self.trials=0;self.evidence=();self.commit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.main,self.sim,self.graph,self.evidence,self.trials,self.commit=advance((self.main,self.sim,self.graph,self.evidence,self.trials,self.commit),a)
  elif a==6:
   if (self.main,self.sim,self.graph,self.evidence,self.trials,self.commit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
