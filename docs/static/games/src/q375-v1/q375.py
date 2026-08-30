"""q375 Vivarium Rig -- assemble dual-effect habitat tools under partner reciprocity."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GLASS,HABITAT,REDIRECT,JOIN,SUPPORT,FAUNA,FAVOR,BAD=14,10,0,9,12,15,6,11,8
LEVELS=[
 {"name":"First Redirect","plan":(1,4)},
 {"name":"Joined Habitat","plan":(2,1,4)},
 {"name":"Support Stratum","plan":(3,2,4,5)},
 {"name":"Dual Effect","plan":(1,3,2,4,5)},
 {"name":"Fair Helper","plan":(2,1,5,3,4,5)},
 {"name":"Vivarium Rig","plan":(3,1,2,5,3,4,1,5)}]
def advance(s,a):
 counts,route,assembled,partner,favor=s;counts=list(counts)
 if a in (1,2,3):counts[a-1]+=1;route=(route+a+counts[a-1])%5
 elif a==4:
  if not sum(counts):return None
  assembled+=1;route=(route+counts[0]*2+counts[1]*3+counts[2])%5;counts=[max(0,v-1) for v in counts]
 elif a==5:favor=(favor+1+(assembled+partner)%2)%4;partner=1-partner;route=(route+favor)%5
 return tuple(counts),route,assembled,partner,favor
def target(x):
 s=((0,0,0),0,0,0,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GLASS;f[9:51,8:56]=HABITAT
  cols=(REDIRECT,JOIN,SUPPORT)
  for i,n in enumerate(g.counts):x=10+i*16;f[11:14,x:x+11]=cols[i];f[16:16+n*6,x:x+11]=cols[i]
  for i in range(g.assembled):f[38+i*4:41+i*4,10:54]=FAUNA
  f[52:55,8:8+g.route*11]=FAUNA;f[56:59,8:8+g.favor*13]=FAVOR
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q375(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self.target=target(LEVELS[0]);self._reset()
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q375",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.counts=(0,0,0);self.route=0;self.assembled=0;self.partner=0;self.favor=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.counts,self.route,self.assembled,self.partner,self.favor),a)
   if s is None:self.bad=True;self.lose()
   else:self.counts,self.route,self.assembled,self.partner,self.favor=s
  elif a==6:
   if (self.counts,self.route,self.assembled,self.partner,self.favor)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
