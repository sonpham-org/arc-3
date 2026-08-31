"""q254 Tessera Pact -- infer a convention while topology macros demand timed interruption."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOLD,SEAM,TILE,OFFER,REPLY,PHASE,CHOICE,BAD=1,6,14,10,4,12,8,11,15
LEVELS=[{"name":"Fair Fold","rule":1,"window":1,"plan":(1,4,5)},{"name":"Recent Seam","rule":2,"window":2,"plan":(2,1,4,4,5,4,4,5)},{"name":"Reciprocal Tile","rule":3,"window":1,"plan":(1,3,2,4,5,4,5,4,5)},{"name":"Macro Courtesy","rule":2,"window":3,"plan":(3,1,2,4,4,4,5,4,4,4,5)},{"name":"Topology Return","rule":3,"window":2,"plan":(2,3,1,4,4,5,4,4,5,4,4,5)},{"name":"Tessera Pact","rule":1,"window":3,"plan":(1,2,3,1,4,4,4,5)}]
def response(rule,a,last,topology):return (rule+a+last+topology)%4
def advance(s,a,x):
 evidence,last,topology,phase,choice=s;evidence=list(evidence)
 if a in (1,2,3):evidence.append((a,response(x["rule"],a,last,topology)));last=a
 elif a==4:
  phase=(phase+1)%4
  if phase==0:topology=1-topology
 elif a==5:
  if phase!=x["window"]:return None
  topology=1-topology;phase=0;choice=(choice+1)%4
 return tuple(evidence),last,topology,phase,choice
def target(x):
 s=((),0,0,0,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOLD
  for i in range(3):x=8+i*18;f[9:34,x:x+14]=SEAM;f[15+i*5:22+i*5,x+4:x+10]=TILE-i
  for i,(_,v) in enumerate(g.evidence[-6:]):f[39+i*3:41+i*3,8:11+v*11]=REPLY
  f[53:56,8:11+g.phase*11]=PHASE;f[57:60,8:11+g.choice*12]=CHOICE;f[36:38,8:20]=OFFER
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q254(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q254",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.last=self.topology=self.phase=self.choice=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.evidence,self.last,self.topology,self.phase,self.choice),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.evidence,self.last,self.topology,self.phase,self.choice=s
  elif a==6:
   if (self.evidence,self.last,self.topology,self.phase,self.choice)==self.target and self.choice==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
