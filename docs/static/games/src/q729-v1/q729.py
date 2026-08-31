"""q729 Reedbed Gradient -- route conserved mass through capacity-changing channels."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,BIN0,BIN1,BIN2,LINK,PHASE,GOAL,BAD=7,10,9,12,14,11,6,13,15
LEVELS=[
 {"name":"First Flow","initial":(2,0,0),"seq":(1,2)},{"name":"Double Flow","initial":(3,0,0),"seq":(1,1,2,2)},
 {"name":"Capacity Link","initial":(4,0,0),"seq":(4,1,1,1,2,2)},{"name":"Rewired Gradient","initial":(4,1,0),"seq":(4,1,2,1,2,4,1,2)},
 {"name":"Phase Channel","initial":(5,1,0),"seq":(4,1,1,2,4,1,2,3,2)},{"name":"Reedbed Gradient","initial":(5,2,1),"seq":(4,1,2,4,1,2,1,2,4,2)}]
def core(s,a,x):
 bins,links,phase,done=s;b=list(bins);cap=2+links.bit_count()
 if a in (1,2):
  src,dst=(0,1) if a==1 else (1,2)
  if not b[src] or b[dst]>=cap:return None
  b[src]-=1;b[dst]+=1
 elif a==3:b=[b[2],b[0],b[1]];phase=(phase+1)%3
 elif a==4:links^=1<<phase;phase=(phase+1)%3
 elif a==5:
  if tuple(b)!=x["goal"] or links!=x["links"] or phase!=x["phase"]:return None
  done=(tuple(b),links,phase)
 return tuple(b),links,phase,done
for x in LEVELS:
 s=(x["initial"],0,0,None)
 for a in x["seq"]:s=core(s,a,x);assert s is not None
 x["goal"],x["links"],x["phase"]=s[0],s[1],s[2];x["plan"]=x["seq"]+(5,)
def target(x):
 s=(x["initial"],0,0,None)
 for a in x["plan"]:s=core(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER
  for i,c in enumerate((BIN0,BIN1,BIN2)):
   x=8+i*17;f[8:33,x:x+14]=c;f[29-g.bins[i]*3:29,x+3:x+11]=GOAL;f[35:38,x:x+g.cfg["goal"][i]*2]=GOAL
  f[43:47,8:8+g.links.bit_count()*12]=LINK;f[51:55,8:8+g.phase*15]=PHASE
  if g.done:f[56:60,39:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q729(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q729",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.links=self.phase=0;self.done=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=core((self.bins,self.links,self.phase,self.done),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.bins,self.links,self.phase,self.done=s
  elif a==6:
   if (self.bins,self.links,self.phase,self.done)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
