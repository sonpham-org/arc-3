"""q726 Backstage Gradient -- route conserved stage mass with signed directional controls."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,BIN0,BIN1,BIN2,POSITIVE,NEGATIVE,GOAL,BAD=6,13,10,14,9,11,8,12,15
LEVELS=[
 {"name":"First Shift","initial":(3,0,0),"seq":(1,)},{"name":"Two Channels","initial":(3,1,0),"seq":(1,2)},
 {"name":"Reverse Flow","initial":(3,1,1),"seq":(1,2,3,2)},{"name":"Signed Gradient","initial":(4,1,1),"seq":(1,1,2,3,2,1)},
 {"name":"Threshold Route","initial":(4,2,1),"seq":(1,2,1,3,2,1,3,1)},{"name":"Backstage Gradient","initial":(5,2,2),"seq":(1,1,2,3,2,1,3,2,1)}]
def advance(s,a,x):
 bins,direction,phase,done=s;b=list(bins)
 if a in (1,2):
  edge=a-1;src,dst=(edge,edge+1) if direction>0 else (edge+1,edge)
  if not b[src] or b[dst]>=6:return None
  b[src]-=1;b[dst]+=1
 elif a==3:direction*=-1;phase=(phase+1)%3
 elif a==4:phase=(phase+1)%3
 elif a==5:
  if (tuple(b),direction,phase)!=x["goal"]:return None
  done=x["goal"]
 return tuple(b),direction,phase,done
for x in LEVELS:
 s=(x["initial"],1,0,None)
 for a in x["seq"]:s=advance(s,a,x);assert s is not None
 x["goal"]=(s[0],s[1],s[2]);x["plan"]=x["seq"]+(5,)
def target(x):
 s=(x["initial"],1,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE
  for i,c in enumerate((BIN0,BIN1,BIN2)):
   x=8+i*17;f[8:33,x:x+14]=c;f[29-g.bins[i]*3:29,x+3:x+11]=GOAL
  f[39:43,8:28]=POSITIVE if g.direction>0 else NEGATIVE;f[47:51,8:8+g.phase*15]=POSITIVE
  if g.done:f[54:59,39:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q726(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q726",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.direction=1;self.phase=0;self.done=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.bins,self.direction,self.phase,self.done),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.bins,self.direction,self.phase,self.done=s
  elif a==6:
   if (self.bins,self.direction,self.phase,self.done)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
