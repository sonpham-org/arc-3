"""q705 Vivarium Evidence -- stop sampling under a fairness-dependent partner policy."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TERRARIUM,FAUNA,TEMP,SAMPLE,FAIR,MARGIN,GOAL,BAD=6,11,14,10,8,9,12,13,15
LEVELS=[
 {"name":"One Sample","seq":(1,)},{"name":"Partner Reading","seq":(2,1)},
 {"name":"Fairness Shift","seq":(3,1,2)},{"name":"Policy Margin","seq":(1,3,2,1)},
 {"name":"Costly Evidence","seq":(2,3,1,2,3,1)},
 {"name":"Vivarium Evidence","seq":(1,2,3,1,3,2,1,2,3)}]
def advance(s,a):
 temp,fairness,partner,samples,margin,stopped=s
 if a==1:margin+=2+partner;samples=samples+((temp,partner,1),);fairness+=1;temp=(temp+1)%6
 elif a==2:margin-=1+int(fairness<0);samples=samples+((temp,partner,-1),);fairness-=2;temp=(temp+2)%6
 elif a==3:partner=int(fairness>=0);fairness=-fairness+partner
 elif a==4:margin=max(-12,min(12,2*margin));temp=(temp+partner)%6
 elif a==5:stopped=(temp,fairness,partner,samples[-4:],margin)
 return temp,fairness,partner,samples,margin,stopped
for x in LEVELS:
 s=(0,0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TERRARIUM
  for i in range(6):x=8+i*8;f[9:29,x:x+6]=TEMP;f[22-(i%3)*5:27-(i%3)*5,x+1:x+5]=FAUNA if i==g.temp else FAIR
  for i,(_,p,sign) in enumerate(g.samples[-5:]):x=8+i*10;f[35:41,x:x+7]=SAMPLE if sign>0 else FAIR;f[42:45,x:x+2+p*3]=FAUNA
  center=31;lo=max(5,min(center,center+g.margin));hi=min(58,max(center,center+g.margin));f[49:54,lo:hi+1]=MARGIN
  f[55:59,8:8+g.partner*25+12]=FAIR
  if g.stopped:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q705(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q705",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.temp=self.fairness=self.partner=self.margin=0;self.samples=();self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.temp,self.fairness,self.partner,self.samples,self.margin,self.stopped=advance((self.temp,self.fairness,self.partner,self.samples,self.margin,self.stopped),a)
  elif a==6:
   if (self.temp,self.fairness,self.partner,self.samples,self.margin,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
