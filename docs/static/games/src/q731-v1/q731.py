"""q731 Pollen Gradient -- route conserved bloom mass across a wear-reversed field."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,BIN0,BIN1,BIN2,WEAR,PHASE,GOAL,BAD=6,14,11,9,12,13,10,8,15
LEVELS=[
 {"name":"First Transfer","initial":(3,0,0),"wear":9,"seq":(1,2)},{"name":"Double Transfer","initial":(3,0,0),"wear":9,"seq":(1,1,2,2)},
 {"name":"Inverted Channel","initial":(3,0,0),"wear":3,"seq":(1,2,4,2)},{"name":"Worn Gradient","initial":(2,1,1),"wear":2,"seq":(1,4,2,1,3)},
 {"name":"Phase Routing","initial":(4,1,1),"wear":3,"seq":(1,2,4,2,1,3,2)},{"name":"Pollen Gradient","initial":(3,2,2),"wear":4,"seq":(1,2,3,1,4,2,1,3,2)}]
def transfer(bins,a,rule):
 b=list(bins)
 if a==1:src,dst=(0,1) if not rule else (1,0)
 else:src,dst=(1,2) if not rule else (2,1)
 if not b[src]:return None
 b[src]-=1;b[dst]+=1;return tuple(b)
def core(s,a,x,commit=False):
 bins,rule,wear,phase,done=s
 if a in (1,2):
  bins=transfer(bins,a,rule)
  if bins is None:return None
  wear+=1
  if wear==x["wear"]:rule^=1
 elif a==3:bins=(bins[2],bins[0],bins[1]);phase=(phase+1)%3
 elif a==4:
  wear+=1;phase=(phase+1)%3
  if wear==x["wear"]:rule^=1
 elif a==5:
  if bins!=x["goal"] or phase!=x["phase"]:return None
  done=(bins,phase)
 return bins,rule,wear,phase,done
for x in LEVELS:
 s=(x["initial"],0,0,0,None)
 for a in x["seq"]:s=core(s,a,x);assert s is not None
 x["goal"],x["phase"]=s[0],s[3];x["plan"]=x["seq"]+(5,)
def target(x):
 s=(x["initial"],0,0,0,None)
 for a in x["plan"]:s=core(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MEADOW
  for i,c in enumerate((BIN0,BIN1,BIN2)):
   x=8+i*17;f[8:33,x:x+14]=c;f[29-g.bins[i]*3:29,x+3:x+11]=GOAL;f[35:38,x:x+min(g.cfg["goal"][i],6)*2]=GOAL
  f[43:47,8:8+min(g.wear,7)*7]=WEAR;f[51:55,8:8+g.phase*15]=PHASE
  if g.done:f[56:60,39:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q731(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q731",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.rule=self.wear=self.phase=0;self.done=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=core((self.bins,self.rule,self.wear,self.phase,self.done),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.bins,self.rule,self.wear,self.phase,self.done=s
  elif a==6:
   if (self.bins,self.rule,self.wear,self.phase,self.done)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
