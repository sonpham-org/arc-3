"""q580 Vault Counter -- shape a rival by redistributing two conserved echo types."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,TACTIC0,TACTIC1,TACTIC2,A_ECHO,B_ECHO,EXPLOIT,BAD=2,11,9,14,10,12,6,13,15
LEVELS=[
 {"name":"Paired Treatment","seq":(1,1)},{"name":"Split Treatment","seq":(1,2)},
 {"name":"Three Treatments","seq":(2,1,2)},{"name":"Dual Counter","seq":(1,2,1,2)},
 {"name":"Passage Swap","seq":(2,2,1,5,2)},{"name":"Vault Counter","seq":(1,2,2,1,5,2)}]
def shape(s,a):
 boxes,hist,rival,exploited=s;b=[list(v) for v in boxes];hist=list(hist)
 if a in (1,2):
  q=a-1;vals=[v[q] for v in b];vals=vals[-1:]+vals[:-1]
  for i,v in enumerate(vals):b[i][q]=v
  hist=(hist+[q])[-3:];rival=(b[1][0]+2*b[2][1]+sum(hist))%3
 elif a==3:b.reverse();rival=(b[1][0]+2*b[2][1]+sum(hist))%3
 elif a==5:b[0],b[2]=b[2],b[0];rival=(b[1][0]+2*b[2][1]+sum(hist))%3
 return tuple(map(tuple,b)),tuple(hist),rival,exploited
for x in LEVELS:
 s=(((2,1),(0,1),(1,0)),(),0,None)
 for a in x["seq"]:s=shape(s,a)
 x["goal"]=s[2];x["plan"]=x["seq"]+(4,)
def advance(s,a,x):
 if a==4:
  if s[2]!=x["goal"]:return None
  return s[0],s[1],s[2],(s[2],s[0])
 return shape(s,a)
def target(x):
 s=(((2,1),(0,1),(1,0)),(),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VAULT
  for i,c in enumerate((TACTIC0,TACTIC1,TACTIC2)):f[8:29,8+i*17:22+i*17]=c
  for i,(a,b) in enumerate(g.boxes):x=10+i*17;f[34:38,x:x+a*4]=A_ECHO;f[41:45,x:x+b*4]=B_ECHO
  f[49:53,8+g.rival*17:22+g.rival*17]=EXPLOIT
  if g.exploited:f[54:59,39:56]=EXPLOIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q580(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q580",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.boxes=((2,1),(0,1),(1,0));self.hist=();self.rival=0;self.exploited=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.boxes,self.hist,self.rival,self.exploited),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.boxes,self.hist,self.rival,self.exploited=s
  elif a==6:
   if (self.boxes,self.hist,self.rival,self.exploited)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
